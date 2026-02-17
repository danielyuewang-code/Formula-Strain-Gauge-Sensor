extern void Strain_Process(void);
extern float Strain_GetForce(void);
extern void CAN_Send_Force(float force);
extern TIM_HandleTypeDef htim2;

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM2)
    {
        Strain_Process();
        float force = Strain_GetForce();
        CAN_Send_Force(force);
    }
}
