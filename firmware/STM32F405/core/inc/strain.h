#ifndef STRAIN_H
#define STRAIN_H

#include "stm32f4xx_hal.h"

void Strain_Init(void);
void Strain_Process(void);
float Strain_GetForce(void);

#endif
