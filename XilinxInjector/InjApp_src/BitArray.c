/*
 * BitArray.c
 *
 *  Created on: 4 Oct 2018
 *      Author: ILYA
 */



#include "xil_types.h"
#include "BitArray.h"


BitArray BitArrayNew(u32 Len){
	BitArray res;
	res.Len = Len;
	for(int i=0;i<MAXWORDS;i++) res.Data[i] = 0;
	return(res);
}

void BitArray_SetBit(BitArray* array, u32 index, u32 val){
	u32 word = index >> 5;
	u32 bit = index & 0x1F;
	u32 mask = ~(1 << bit);
	array->Data[word] = (array->Data[word] & mask) | (val << bit)  ;
}

u32 BitArray_GetBit(BitArray array, u32 index){
	u32 word = index >> 5;
	u32 bit = index & 0x1F;
	return((array.Data[word] >> bit) & 0x1);
}

u32 CountOnes(BitArray array){
	u32 res = 0;
	u32 last_word_index = (array.Len >> 5) + (array.Len & 0x1F > 0 ? 1 : 0);
	for(int word=0;word<last_word_index;word++){
		for(int i=0;i<32;i++){
			if((array.Data[word] >> i) & 1) res++;
		}
	}
	return(res);
}




