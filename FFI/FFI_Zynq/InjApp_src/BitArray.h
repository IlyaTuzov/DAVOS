/*
 * BitArray.h
 *
 *  Created on: 4 Oct 2018
 *      Author: ILYA
 */

#ifndef SRC_BITARRAY_H_
#define SRC_BITARRAY_H_

#define MAXWORDS 10
typedef struct{
	u32 Len;
	u32 Data[MAXWORDS];
} BitArray;

BitArray BitArrayNew(u32 Len);
void BitArray_SetBit(BitArray* array, u32 index, u32 val);
u32 BitArray_GetBit(BitArray array, u32 index);
u32 CountOnes(BitArray array);

#endif /* SRC_BITARRAY_H_ */
