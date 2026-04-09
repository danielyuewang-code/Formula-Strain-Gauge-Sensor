/**
 * strain_gauge_firmware.c
 * 
 * STM32 Firmware — Strain Gauge Data Acquisition System
 * Formula Racing SAE — UBC
 * 
 * What this firmware does:
 * 1. ADC continuously reads raw voltage from strain gauge amplifier via DMA
 * 2. DMA moves ADC readings into memory automatically (no CPU involvement)
 * 3. Timer fires at 100Hz
 * 4. CAN transmits raw ADC values to AIM data logger at 100Hz
 * 
 * All calibration and filtering done in post-processing (Python pipeline)
 */

#include "stm32f4xx_hal.h"
#include <stdint.h>

/* ─────────────────────────────────────────────────────────
   HARDWARE HANDLES
   Structs HAL uses to track the state of each peripheral.
   Pass these into every HAL function call.
   ───────────────────────────────────────────────────────── */
ADC_HandleTypeDef hadc1;
DMA_HandleTypeDef hdma_adc1;
CAN_HandleTypeDef hcan1;
TIM_HandleTypeDef htim2;

/* ─────────────────────────────────────────────────────────
   CONSTANTS
   ───────────────────────────────────────────────────────── */
#define NUM_CHANNELS  4    // FL, FR, RL, RR strain gauges

/* ─────────────────────────────────────────────────────────
   BUFFERS
   ───────────────────────────────────────────────────────── */

/**
 * DMA buffer — ADC results land here automatically in hardware
 *
 * volatile: this memory is written by DMA hardware outside of
 * normal code flow, so compiler must always read it fresh
 *
 * Layout: [CH0, CH1, CH2, CH3] — one uint16 per channel
 * Each value is a 12-bit ADC count (0 to 4095)
 */
volatile uint16_t adc_dma_buffer[NUM_CHANNELS];

/**
 * 100Hz transmit flag — set by timer ISR, cleared by main loop
 */
volatile uint8_t can_transmit_flag = 0;

/* ─────────────────────────────────────────────────────────
   FUNCTION DECLARATIONS
   ───────────────────────────────────────────────────────── */
void SystemClock_Config(void);
void MX_ADC1_Init(void);
void MX_DMA_Init(void);
void MX_CAN1_Init(void);
void MX_TIM2_Init(void);
void transmit_can_message(void);
void Error_Handler(void);

/* ─────────────────────────────────────────────────────────
   MAIN
   ───────────────────────────────────────────────────────── */
int main(void)
{
    HAL_Init();
    SystemClock_Config();

    /* DMA must init before ADC */
    MX_DMA_Init();
    MX_ADC1_Init();
    MX_CAN1_Init();
    MX_TIM2_Init();

    /**
     * Start ADC in DMA circular mode
     * ADC scans all 4 channels continuously
     * DMA writes each result into adc_dma_buffer automatically
     * CPU does nothing — hardware handles it
     */
    if (HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_dma_buffer, NUM_CHANNELS) != HAL_OK)
    {
        Error_Handler();
    }

    /* Start CAN peripheral */
    if (HAL_CAN_Start(&hcan1) != HAL_OK)
    {
        Error_Handler();
    }

    /**
     * Start timer interrupt at 100Hz
     * Every 10ms the timer ISR sets can_transmit_flag = 1
     */
    if (HAL_TIM_Base_Start_IT(&htim2) != HAL_OK)
    {
        Error_Handler();
    }

    /* ── MAIN LOOP ── */
    while (1)
    {
        /**
         * Check if 100Hz timer has fired
         * If yes — transmit whatever is currently in adc_dma_buffer
         * DMA is continuously keeping that buffer up to date
         */
        if (can_transmit_flag)
        {
            can_transmit_flag = 0;
            transmit_can_message();
        }
    }
}

/* ─────────────────────────────────────────────────────────
   CAN TRANSMISSION
   
   Packs raw ADC values into CAN message and sends to AIM logger.
   
   4 channels x 2 bytes = 8 bytes — fits exactly in one CAN frame.
   
   AIM logger receives raw ADC counts.
   Python pipeline later converts counts to voltage to force.
   ───────────────────────────────────────────────────────── */
void transmit_can_message(void)
{
    CAN_TxHeaderTypeDef TxHeader;
    uint8_t TxData[8];
    uint32_t TxMailbox;

    TxHeader.StdId = 0x123;        // Custom ID — AIM logger listens for this
    TxHeader.IDE   = CAN_ID_STD;   // Standard 11-bit ID
    TxHeader.RTR   = CAN_RTR_DATA; // Data frame
    TxHeader.DLC   = 8;            // 8 bytes of payload

    /**
     * Pack 4 raw ADC values (uint16) into 8 bytes
     * Each value split into high byte and low byte
     *
     * Example: ADC reads 2048 (0x0800)
     * TxData[0] = 0x08  (high byte)
     * TxData[1] = 0x00  (low byte)
     *
     * AIM reassembles: (0x08 << 8) | 0x00 = 2048
     * Python then converts 2048 counts to voltage to force
     */
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++)
    {
        TxData[ch * 2]     = (uint8_t)((adc_dma_buffer[ch] >> 8) & 0xFF); // high byte
        TxData[ch * 2 + 1] = (uint8_t)(adc_dma_buffer[ch] & 0xFF);        // low byte
    }

    if (HAL_CAN_AddTxMessage(&hcan1, &TxHeader, TxData, &TxMailbox) != HAL_OK)
    {
        Error_Handler();
    }
}

/* ─────────────────────────────────────────────────────────
   TIMER ISR CALLBACK
   
   Called by HAL every time Timer 2 fires (every 10ms = 100Hz)
   Just sets the flag — transmission happens in main loop
   Keeps ISR as short as possible
   ───────────────────────────────────────────────────────── */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM2)
    {
        can_transmit_flag = 1;
    }
}

/* ─────────────────────────────────────────────────────────
   ADC INIT
   4 channels, 12-bit, continuous scan, DMA enabled
   ───────────────────────────────────────────────────────── */
void MX_ADC1_Init(void)
{
    ADC_ChannelConfTypeDef sConfig = {0};

    hadc1.Instance                   = ADC1;
    hadc1.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV4;
    hadc1.Init.Resolution            = ADC_RESOLUTION_12B;      // 0 to 4095
    hadc1.Init.ScanConvMode          = ENABLE;                  // Scan all 4 channels
    hadc1.Init.ContinuousConvMode    = ENABLE;                  // Keep scanning forever
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion       = NUM_CHANNELS;
    hadc1.Init.DMAContinuousRequests = ENABLE;                  // DMA keeps running

    if (HAL_ADC_Init(&hadc1) != HAL_OK) Error_Handler();

    uint32_t channels[NUM_CHANNELS] = {
        ADC_CHANNEL_0,  // Front Left
        ADC_CHANNEL_1,  // Front Right
        ADC_CHANNEL_2,  // Rear Left
        ADC_CHANNEL_3   // Rear Right
    };

    for (uint8_t i = 0; i < NUM_CHANNELS; i++)
    {
        sConfig.Channel      = channels[i];
        sConfig.Rank         = i + 1;
        sConfig.SamplingTime = ADC_SAMPLETIME_480CYCLES;
        if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) Error_Handler();
    }
}

/* ─────────────────────────────────────────────────────────
   DMA INIT
   DMA2 Stream0 Channel0 is hardware-fixed for ADC1 on STM32F4
   Circular mode — wraps back to start of buffer automatically
   ───────────────────────────────────────────────────────── */
void MX_DMA_Init(void)
{
    __HAL_RCC_DMA2_CLK_ENABLE();

    hdma_adc1.Instance                 = DMA2_Stream0;
    hdma_adc1.Init.Channel             = DMA_CHANNEL_0;
    hdma_adc1.Init.Direction           = DMA_PERIPH_TO_MEMORY;    // ADC to buffer
    hdma_adc1.Init.PeriphInc           = DMA_PINC_DISABLE;        // ADC register fixed
    hdma_adc1.Init.MemInc              = DMA_MINC_ENABLE;         // Step through buffer
    hdma_adc1.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD; // 16-bit ADC result
    hdma_adc1.Init.MemDataAlignment    = DMA_MDATAALIGN_HALFWORD; // 16-bit buffer
    hdma_adc1.Init.Mode                = DMA_CIRCULAR;            // Wrap automatically
    hdma_adc1.Init.Priority            = DMA_PRIORITY_HIGH;

    if (HAL_DMA_Init(&hdma_adc1) != HAL_OK) Error_Handler();
    __HAL_LINKDMA(&hadc1, DMA_Handle, hdma_adc1);
}

/* ─────────────────────────────────────────────────────────
   CAN INIT — 1Mbit/s
   ───────────────────────────────────────────────────────── */
void MX_CAN1_Init(void)
{
    hcan1.Instance                  = CAN1;
    hcan1.Init.Prescaler            = 3;
    hcan1.Init.Mode                 = CAN_MODE_NORMAL;
    hcan1.Init.SyncJumpWidth        = CAN_SJW_1TQ;
    hcan1.Init.TimeSeg1             = CAN_BS1_11TQ;
    hcan1.Init.TimeSeg2             = CAN_BS2_2TQ;
    hcan1.Init.AutoBusOff           = ENABLE;
    hcan1.Init.AutoRetransmission   = ENABLE;
    hcan1.Init.TimeTriggeredMode    = DISABLE;
    hcan1.Init.AutoWakeUp           = DISABLE;
    hcan1.Init.ReceiveFifoLocked    = DISABLE;
    hcan1.Init.TransmitFifoPriority = DISABLE;

    if (HAL_CAN_Init(&hcan1) != HAL_OK) Error_Handler();

    /* Accept all messages — we're only transmitting anyway */
    CAN_FilterTypeDef filter = {0};
    filter.FilterActivation     = CAN_FILTER_ENABLE;
    filter.FilterBank           = 0;
    filter.FilterFIFOAssignment = CAN_RX_FIFO0;
    filter.FilterMode           = CAN_FILTERMODE_IDMASK;
    filter.FilterScale          = CAN_FILTERSCALE_32BIT;

    if (HAL_CAN_ConfigFilter(&hcan1, &filter) != HAL_OK) Error_Handler();
}

/* ─────────────────────────────────────────────────────────
   TIMER INIT — 100Hz interrupt
   
   84MHz / (prescaler 840 x period 1000) = 100Hz exactly
   ───────────────────────────────────────────────────────── */
void MX_TIM2_Init(void)
{
    htim2.Instance               = TIM2;
    htim2.Init.Prescaler         = 840 - 1;
    htim2.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim2.Init.Period            = 1000 - 1;
    htim2.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    if (HAL_TIM_Base_Init(&htim2) != HAL_OK) Error_Handler();
}

/* ─────────────────────────────────────────────────────────
   ERROR HANDLER
   ───────────────────────────────────────────────────────── */
void Error_Handler(void)
{
    __disable_irq();
    while (1) {}
}
