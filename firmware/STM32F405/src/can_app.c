#include "main.h"
#include "can_app.h"

extern CAN_HandleTypeDef hcan;

void CAN_App_Init(void)
{
    HAL_CAN_Start(&hcan);
}

void CAN_Send_Force(float force)
{
    CAN_TxHeaderTypeDef txHeader;
    uint8_t txData[8];
    uint32_t txMailbox;

    int16_t force_scaled = (int16_t)(force * 10.0f); // 0.1N resolution

    txHeader.StdId = 0x201;
    txHeader.ExtId = 0;
    txHeader.RTR = CAN_RTR_DATA;
    txHeader.IDE = CAN_ID_STD;
    txHeader.DLC = 2;
    txHeader.TransmitGlobalTime = DISABLE;

    txData[0] = (force_scaled >> 8) & 0xFF;
    txData[1] = force_scaled & 0xFF;

    HAL_CAN_AddTxMessage(&hcan, &txHeader, txData, &txMailbox);
}
