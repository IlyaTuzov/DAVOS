// A CUDA-powered tool to quickly rank all possible factorial configurations attending to input scenarios (Weighted-Sum models)
// A set of factors is inferred from input regression models
// Optimization results are exported into XML-formatted file
// Author: Ilya Tuzov, Universitat Politecnica de Valencia

#include "cuda_runtime.h"
#include "device_launch_parameters.h"


#include <stdio.h>
#include <vector>
#include <regex>
#include <string>
#include <stdint.h>
#include <iostream>
#include <fstream>
#include "tinyxml2.h"
#include <cmath>
#include <math.h>

using namespace std;
using namespace tinyxml2;

#ifndef XMLCheckResult
#define XMLCheckResult(a_eResult) if (a_eResult != XML_SUCCESS) { printf("Error: %i\n", a_eResult); }
#endif

static void HandleError(cudaError_t err,
	const char *file,
	int line) {
	if (err != cudaSuccess) {
		printf("%s in %s at line %d\n", cudaGetErrorString(err), file, line);
	}
}
#define HANDLE_ERROR( err ) (HandleError( err, __FILE__, __LINE__ ))



//-----------------

#define MAX_POINTS_PER_THREAD 4096
#define NBLOCKS 16
#define NTHREADS 512
#define CU_RESULT_LEN NBLOCKS*NTHREADS
#define MAX_MODELS 10
#define MAX_FACTORS 33
#define MAX_INTERACTIONS MAX_FACTORS*8
#define FACTOR_VECTOR_SIZE MAX_FACTORS*MAX_MODELS
#define INTERACTION_VECTOR_SIZE MAX_INTERACTIONS*MAX_MODELS


enum distribution_t {normal, gamma, inverse_gaussian, poisson, undefined};

struct t_estimator_factor {
	string factor;
	int id;
	float value;
	int response_variable_id;
};

struct t_estimator_interaction {
	string factor_1;
	string factor_2;
	int id_1;
	int id_2;
	float value;
	int response_variable_id;
};

struct t_response_variable{
	int id;
	string name;
	string model_filename;
	float intercept;
	float treshold;
	distribution_t dist;
};


struct t_factor_desc{
	string name;
	int id;
};

//returns index of structure for given keyname [0 : i_desc-size()-1]
//if does not exists - returns -1
int get_index(std::vector<t_factor_desc> i_desc, string keyname){
	for (int i = 0; i < i_desc.size(); i++){
		if (i_desc[i].name == keyname) return(i);
	};
	return(-1);
}

//returns id of structure for given keyname [0 : i_desc-size()-1]
//if does not exists - returns -1
int get_id(std::vector<t_factor_desc> i_desc, string keyname){
	for (int i = 0; i < i_desc.size(); i++){
		if (i_desc[i].name == keyname) return(i_desc[i].id);
	};
	return(-1);
}

bool compare_by_name(const t_factor_desc & a, const t_factor_desc & b){
	return(a.name < b.name);
}

//structures optimized for cuda operations
struct cu_factor_estimator{
	int id;
	float value;
	int response_variable_id;
};

struct cu_interaction_estimator{
	int id_1;
	int id_2;
	float value;
	int response_variable_id;
};

struct cu_response_variable{
	int id;
	distribution_t dist;
	float intercept;
	int factor_first;
	int factor_num;
	int interaction_first;
	int interaction_num;
	//computed/updated after first kernell call, entire structure should be re-copied to device constant memory
	float max;
	float min;
};

//Kernel return type
struct cu_thread_result{
	uint64_t max_index;
	uint64_t min_index;
	float max;
	float min;
};

struct input_data_desctiptor{
	int real_models;
	int real_factor_estimators;
	int real_interaction_estimators;
	uint64_t factor_vector_len;
};

struct cu_job_descriptor{
	uint64_t max_index;			//2 ^ input_data_desctiptor.real_factor_estimators
	uint64_t points_per_thread;	//max_index / CU_RESULT_LEN
};



enum minmax_t { v_min, v_max, v_undefined };

struct t_implementation_goal_item {
	minmax_t goal;
	string var_name;
	int var_id;
	float weight;
};

struct t_implementation_goal {
	string goal_name;
	t_implementation_goal_item items[MAX_MODELS];
	int valid_items_num;
};

struct cu_implementation_goal_item {
	minmax_t goal;
	int var_id;
	float weight;
};


//Global variables and functions

cu_factor_estimator *host_factor_vector;
cu_interaction_estimator  *host_interaction_vector;
cu_response_variable *host_response_variables;
input_data_desctiptor host_data_descriptor;
cu_job_descriptor host_job_descriptor;
cu_implementation_goal_item *host_implementation_goal;

__constant__ cu_factor_estimator			cuda_factor_vector[FACTOR_VECTOR_SIZE];
__constant__ cu_interaction_estimator		cuda_interaction_vector[INTERACTION_VECTOR_SIZE];
__constant__ cu_response_variable			cuda_response_variables[MAX_MODELS];
__constant__ input_data_desctiptor			cuda_data_descriptor[1];
__constant__ cu_job_descriptor				cuda_jobdesc[1];
__constant__ cu_implementation_goal_item	cuda_implementation_goal[MAX_MODELS];

//Dummy function required to cope with cudaMemcpyToSymbol bug
__constant__ float dev_test_arr[10];
 float tiny_test_arr[10];
 void dummy_wakeup_const_memory(){
	 for (int i = 0; i < 10; i++)tiny_test_arr[i] = float(i) + 1.5;
	 HANDLE_ERROR(cudaMemcpyToSymbol(dev_test_arr, tiny_test_arr, 10 * sizeof(float)));
 }
 //end dummy code

 //**** AUXILIARY FUNCTIONS (on-host)
 t_estimator_factor * get_estimator_for_model_ptr(std::vector<t_estimator_factor> v_factors, string ifactor, int ivar_id){
	 for (int i = 0; i < v_factors.size(); i++){
		 if ((v_factors[i].factor == ifactor) && (v_factors[i].response_variable_id == ivar_id))
			 return(&v_factors[i]);
	 }
	 return(nullptr);
 }

 t_estimator_factor * get_estimator_any_ptr(std::vector<t_estimator_factor> v_factors, string ifactor){
	 for (int i = 0; i < v_factors.size(); i++){
		 if (v_factors[i].factor == ifactor )
			 return(&v_factors[i]);
	 }
	 return(nullptr);
 }

//******************* HOST Functions
cu_thread_result compute_min_max_on_host(int var_id){
	cu_thread_result res = { 0, 0, 0, 0 };
	bool min_initialized = false, max_initialized = false;
	unsigned int factor_vect[MAX_FACTORS];
	register uint64_t c = 0;
	register uint64_t j = 0;
	uint64_t pp_step = host_job_descriptor.max_index / uint64_t(100);
	uint64_t pp_cnt = 0;
	int pp_progress = 0;
	//
	cout << "\n";
	for (c = 0; c < host_job_descriptor.max_index; c++){
		if (c > pp_cnt){
			cout << "\rCOMPUTE_MIN_MAX progress: " << pp_progress << "%";
			pp_cnt += pp_step;
			pp_progress += 1;
		}
		for (j = 0; j < host_data_descriptor.factor_vector_len; j++)
			factor_vect[j] = unsigned int((c >> j) & uint64_t(1));
		float current = host_response_variables[var_id].intercept;
		//process single-factor estimators
		for (int i = host_response_variables[var_id].factor_first; i < host_response_variables[var_id].factor_first + host_response_variables[var_id].factor_num; i++){
			if (factor_vect[host_factor_vector[i].id] == 1) current += host_factor_vector[i].value;
		}
		//process interactions estimators
		for (int i = host_response_variables[var_id].interaction_first; i < host_response_variables[var_id].interaction_first + host_response_variables[var_id].interaction_num; i++){
			if ((factor_vect[host_interaction_vector[i].id_1] == 1) && (factor_vect[host_interaction_vector[i].id_2] == 1)) current += host_interaction_vector[i].value;
		}
		if (host_response_variables[var_id].dist == gamma) current = 1 / current;
		else if (host_response_variables[var_id].dist == inverse_gaussian) current = 1 / std::sqrtf(current);
		else if (host_response_variables[var_id].dist == poisson) current = std::expf(current);
		if (min_initialized && max_initialized){
			if (current < res.min){
				res.min = current;
				res.min_index = c;
			}
			if (current > res.max){
				res.max = current;
				res.max_index = c;
			}
		}
		else{
			res.min = current; res.max = current;
			min_initialized = true; max_initialized = true;
		}
	};
	return(res);
}


//CUDA FUNCTIONS
__global__ void cu_min_max(int var_id, uint64_t start_index,  cu_thread_result * res_arr)
{
	unsigned int factor_vect[MAX_FACTORS];
	bool min_initialized = false, max_initialized = false;
	cu_thread_result res = { 0, 0, 0, 0 };
	uint64_t idx = uint64_t(blockIdx.x * blockDim.x + threadIdx.x);
	uint64_t offset = idx*cuda_jobdesc[0].points_per_thread;
	uint64_t loc_offset = start_index + offset;

	uint64_t c = 0;
	uint64_t j = 0;
	for (c = loc_offset; (c < loc_offset + cuda_jobdesc[0].points_per_thread) && (c < cuda_jobdesc[0].max_index); c++){
		for (j = 0; j < cuda_data_descriptor[0].factor_vector_len; j++)
			factor_vect[j] = unsigned int((c >> j) & uint64_t(1));		
		float current = cuda_response_variables[var_id].intercept;
		//process single-factor estimators
		for (int i = cuda_response_variables[var_id].factor_first; i < cuda_response_variables[var_id].factor_first + cuda_response_variables[var_id].factor_num; i++){
			if (factor_vect[cuda_factor_vector[i].id] == 1) current += cuda_factor_vector[i].value;
		}
		//process interactions estimators
		for (int i = cuda_response_variables[var_id].interaction_first; i < cuda_response_variables[var_id].interaction_first + cuda_response_variables[var_id].interaction_num; i++){
			if ((factor_vect[cuda_interaction_vector[i].id_1] == 1) && (factor_vect[cuda_interaction_vector[i].id_2] == 1)) current += cuda_interaction_vector[i].value;
		}
		if (cuda_response_variables[var_id].dist == gamma) current = 1 / current;
		else if (cuda_response_variables[var_id].dist == inverse_gaussian) current = 1/std::sqrtf(current);
		else if (cuda_response_variables[var_id].dist == poisson) current = std::expf(current);
		if (min_initialized && max_initialized){
			if (current < res.min){
				res.min = current;
				res.min_index = c;
			}
			if (current > res.max){
				res.max = current;
				res.max_index = c;
			}
		}
		else{
			res.min = current; res.max = current;
			res.min_index = c; res.max_index = c;
			min_initialized = true; max_initialized = true;
		}
	};
	if (offset < cuda_jobdesc[0].max_index){
		res_arr[idx] = res;
		//printf("\nc=%u, min_val =%f, min id = %u, max_val=%f, max id = %u", c, res.min, res.min_index, res.max, res.max_index);
	}

}



__host__ cu_thread_result compute_min_max_on_cuda(int var_id){
	cu_thread_result res = { 0, 0, 0, 0 };
	int dev_result_len = (CU_RESULT_LEN < host_job_descriptor.max_index) ? CU_RESULT_LEN : host_job_descriptor.max_index;
	cu_thread_result * dev_res_arr;
	HANDLE_ERROR(cudaMalloc((void**)&dev_res_arr, dev_result_len * sizeof(cu_thread_result)));
	cu_thread_result * host_res_arr = (cu_thread_result*)malloc(sizeof(cu_thread_result)* dev_result_len);

	int iterations = host_job_descriptor.max_index / (dev_result_len*host_job_descriptor.points_per_thread);
	float progress_step=100.0, progress = 0.0;
	if (iterations > 1){
		progress_step = 100.0 / float(iterations);
	};
	for (uint64_t c = 0; c < host_job_descriptor.max_index; c += dev_result_len*host_job_descriptor.points_per_thread){
		progress += progress_step;
		printf("\rCompute min/max on CUDA, variable [%i], progress: %2.2f%%", var_id, progress);
		cu_min_max << < NBLOCKS, NTHREADS >> > (var_id, c, dev_res_arr);
		cudaDeviceSynchronize();
		HANDLE_ERROR(cudaMemcpy(host_res_arr, dev_res_arr, dev_result_len * sizeof(cu_thread_result), cudaMemcpyDeviceToHost));
		if (c == 0)res = host_res_arr[0];
		for (int i = 0; i < dev_result_len; i++){
			if (host_res_arr[i].min < res.min){
				res.min = host_res_arr[i].min;
				res.min_index = host_res_arr[i].min_index;
			};
			if (host_res_arr[i].max > res.max){
				res.max = host_res_arr[i].max;
				res.max_index = host_res_arr[i].max_index;
			};
		}
		//printf("\n\nmin = %f, max = %f", res.min, res.max);
	}
	cudaFree(dev_res_arr);
	return(res);
}

//Implementation goals on Cuda
__global__ void cu_implementation_goal(int valid_items_num, uint64_t start_index, cu_thread_result * res_arr)
{
	unsigned int factor_vect[MAX_FACTORS];
	bool min_initialized = false, max_initialized = false;
	cu_thread_result res = { 0, 0, 0, 0 };
	uint64_t idx = uint64_t(blockIdx.x * blockDim.x + threadIdx.x);
	uint64_t offset = idx*cuda_jobdesc[0].points_per_thread;
	uint64_t loc_offset = start_index + offset;

	uint64_t c = 0;
	uint64_t j = 0;
	for (c = loc_offset; (c < loc_offset + cuda_jobdesc[0].points_per_thread) && (c < cuda_jobdesc[0].max_index); c++){
		for (j = 0; j < cuda_data_descriptor[0].factor_vector_len; j++)
			factor_vect[j] = unsigned int((c >> j) & uint64_t(1));

		float goal_current=0;
		for (int t = 0; t < valid_items_num; t++){
			int var_id = cuda_implementation_goal[t].var_id;
			float var_current = cuda_response_variables[var_id].intercept;
			//process single-factor estimators
			for (int i = cuda_response_variables[var_id].factor_first; i < cuda_response_variables[var_id].factor_first + cuda_response_variables[var_id].factor_num; i++){
				if (factor_vect[cuda_factor_vector[i].id] == 1) var_current += cuda_factor_vector[i].value;
			}
			//process interactions estimators
			for (int i = cuda_response_variables[var_id].interaction_first; i < cuda_response_variables[var_id].interaction_first + cuda_response_variables[var_id].interaction_num; i++){
				if ((factor_vect[cuda_interaction_vector[i].id_1] == 1) && (factor_vect[cuda_interaction_vector[i].id_2] == 1)) var_current += cuda_interaction_vector[i].value;
			}
			if (cuda_response_variables[var_id].dist == gamma) var_current = 1 / var_current;
			else if (cuda_response_variables[var_id].dist == inverse_gaussian) var_current = 1 / std::sqrtf(var_current);
			else if (cuda_response_variables[var_id].dist == poisson) var_current = std::expf(var_current);
			//normalize: min or max
			float normalized_current;
			float minv = cuda_response_variables[var_id].min;
			float maxv = cuda_response_variables[var_id].max;
			if (minv > 0){
				if (cuda_implementation_goal[t].goal == v_min) normalized_current = minv / var_current;
				else if (cuda_implementation_goal[t].goal == v_max) normalized_current = var_current/ maxv;
			}
			else if(maxv > 0){
				if (cuda_implementation_goal[t].goal == v_min) normalized_current = (minv+0.1) / (var_current+0.1);
				else if (cuda_implementation_goal[t].goal == v_max) normalized_current = var_current / maxv;
			}
			else{
				normalized_current = 1;
			}
			//*weight and add to goal sum
			goal_current += (normalized_current*cuda_implementation_goal[t].weight);
		}

		if (min_initialized && max_initialized){
			if (goal_current < res.min){
				res.min = goal_current;
				res.min_index = c;
			}
			if (goal_current > res.max){
				res.max = goal_current;
				res.max_index = c;
			}
		}
		else{
			res.min = goal_current; res.max = goal_current;
			res.min_index = c; res.max_index = c;
			min_initialized = true; max_initialized = true;
		}
	};
	if (offset < cuda_jobdesc[0].max_index){
		res_arr[idx] = res;
		//printf("\nc=%u, min_val =%f, min id = %u, max_val=%f, max id = %u", c, res.min, res.min_index, res.max, res.max_index);
	}
}


__host__ cu_thread_result process_implementation_goal_on_cuda(int valid_items_num){
	cu_thread_result res = { 0, 0, 0, 0 };
	for (int i = 0; i < valid_items_num; i++)printf("\n\t\t\tVar_id = %i\tGoal = %i\tWeight = %f", host_implementation_goal[i].var_id, host_implementation_goal[i].goal, host_implementation_goal[i].weight);
	printf("\n");
	int dev_result_len = (CU_RESULT_LEN < host_job_descriptor.max_index) ? CU_RESULT_LEN : host_job_descriptor.max_index;
	cu_thread_result * dev_res_arr;
	HANDLE_ERROR(cudaMalloc((void**)&dev_res_arr, dev_result_len * sizeof(cu_thread_result)));
	cu_thread_result * host_res_arr = (cu_thread_result*)malloc(sizeof(cu_thread_result)* dev_result_len);

	int iterations = host_job_descriptor.max_index / (dev_result_len*host_job_descriptor.points_per_thread);
	float progress_step = 100.0, progress = 0.0;
	if (iterations > 1){
		progress_step = 100.0 / float(iterations);
	};
	for (uint64_t c = 0; c < host_job_descriptor.max_index; c += dev_result_len*host_job_descriptor.points_per_thread){
		progress += progress_step;
		printf("\rProcess implementation goal on CUDA, progress: %2.2f%%",  progress);
		cu_implementation_goal << < NBLOCKS, NTHREADS >> > (valid_items_num, c, dev_res_arr);
		cudaDeviceSynchronize();
		HANDLE_ERROR(cudaMemcpy(host_res_arr, dev_res_arr, dev_result_len * sizeof(cu_thread_result), cudaMemcpyDeviceToHost));
		if (c == 0)res = host_res_arr[0];
		for (int i = 0; i < dev_result_len; i++){
			if (host_res_arr[i].min < res.min){
				res.min = host_res_arr[i].min;
				res.min_index = host_res_arr[i].min_index;
			};
			if (host_res_arr[i].max > res.max){
				res.max = host_res_arr[i].max;
				res.max_index = host_res_arr[i].max_index;
			};
		}
		//printf("\n\nmin = %f, max = %f", res.min, res.max);
	}
	cudaFree(dev_res_arr);
	return(res);
}

float get_varvalue(int var_id, uint64_t confnum){
	unsigned int factor_vect[MAX_FACTORS];
	register uint64_t j = 0;
	for (j = 0; j < host_data_descriptor.factor_vector_len; j++)
		factor_vect[j] = unsigned int((confnum >> j) & uint64_t(1));
	float res = host_response_variables[var_id].intercept;
	//process single-factor estimators
	for (int i = host_response_variables[var_id].factor_first; i < host_response_variables[var_id].factor_first + host_response_variables[var_id].factor_num; i++){
		if (factor_vect[host_factor_vector[i].id] == 1) res += host_factor_vector[i].value;
	}
	//process interactions estimators
	for (int i = host_response_variables[var_id].interaction_first; i < host_response_variables[var_id].interaction_first + host_response_variables[var_id].interaction_num; i++){
		if ((factor_vect[host_interaction_vector[i].id_1] == 1) && (factor_vect[host_interaction_vector[i].id_2] == 1)) res += host_interaction_vector[i].value;
	}
	if (host_response_variables[var_id].dist == gamma) res = 1 / res;
	else if (host_response_variables[var_id].dist == inverse_gaussian) res = 1 / std::sqrtf(res);
	else if (host_response_variables[var_id].dist == poisson) res = std::expf(res);
	return(res);
}

string get_configvector_csv(std::vector<t_factor_desc> factors, uint64_t config_num){
	string res = "";
	unsigned int factor_vect[MAX_FACTORS];
	int size = factors.size();
	register uint64_t j = 0;
	for (int i = 0; i < size; i++)res += factors[i].name + ",";
	res += "\n";
	for (j = 0; j < host_data_descriptor.factor_vector_len; j++){
		factor_vect[j] = unsigned int((config_num >> j) & uint64_t(1));
		res += std::to_string(factor_vect[j]) + ",\t";
	}
	return(res);
}

string get_fullconfigvector_csv(std::vector<string> full_factor_set, std::vector<t_factor_desc> factors, uint64_t config_num, bool labels){
	unsigned int factor_vect[MAX_FACTORS];
	string part_1="", part_2="";
	register uint64_t j = 0;
	for (j = 0; j < host_data_descriptor.factor_vector_len; j++)
		factor_vect[j] = unsigned int((config_num >> j) & uint64_t(1));
	int bit_cnt = 0;
	for (int i = 0; i < full_factor_set.size(); i++){
		part_1 += full_factor_set[i];
		if (get_id(factors, full_factor_set[i]) < 0){
			part_2 += "-";
		}
		else{
			part_2 += std::to_string(factor_vect[bit_cnt]);
			bit_cnt += 1;
		};
		if (i < full_factor_set.size() - 1){
			part_1 += ",";
			part_2 += ",  ";
		}
	}
	if (labels == true) return(part_1 + "\n" + part_2);
	else return(part_2);
}

string get_fullconfigvector_significant_only_csv(std::vector<string> full_factor_set, std::vector<t_factor_desc> factors, std::vector<t_factor_desc> significant_factors, uint64_t config_num, bool labels){
	unsigned int factor_vect[MAX_FACTORS];
	string part_1 = "", part_2 = "";
	register uint64_t j = 0;
	for (j = 0; j < host_data_descriptor.factor_vector_len; j++)
		factor_vect[j] = unsigned int((config_num >> j) & uint64_t(1));
	int bit_cnt = 0;
	for (int i = 0; i < full_factor_set.size(); i++){
		part_1 += full_factor_set[i];
		if (get_id(factors, full_factor_set[i]) < 0){
			part_2 += "-";
		}
		else{
			if (get_id(significant_factors, full_factor_set[i]) < 0){
				part_2 += "-";
			}
			else{
				part_2 += std::to_string(factor_vect[bit_cnt]);
			}
			bit_cnt += 1;
		};
		if (i < full_factor_set.size() - 1){
			part_1 += ",";
			part_2 += ",  ";
		}
	}
	if (labels == true) return(part_1 + "\n" + part_2);
	else return(part_2);
}

string get_fullconfigvector_varid_specific_csv(std::vector<string> full_factor_set, std::vector<t_estimator_factor> v_factors, int response_variable_id, uint64_t config_num, bool labels){
	unsigned int factor_vect[MAX_FACTORS];
	string part_1 = "", part_2 = "";
	register uint64_t j = 0;
	for (j = 0; j < host_data_descriptor.factor_vector_len; j++)
		factor_vect[j] = unsigned int((config_num >> j) & uint64_t(1));
	int bit_cnt = 0;
	for (int i = 0; i < full_factor_set.size(); i++){
		part_1 += full_factor_set[i];
		if (get_estimator_for_model_ptr(v_factors, full_factor_set[i], response_variable_id) == nullptr){
			part_2 += "-";
		}
		else{
			part_2 += std::to_string(factor_vect[bit_cnt]);
		};
		if (get_estimator_any_ptr(v_factors, full_factor_set[i]) != nullptr) bit_cnt += 1;
		if (i < full_factor_set.size() - 1){
			part_1 += ",";
			part_2 += ",  ";
		}
	}
	if(labels == true) return(part_1 + "\n" + part_2);
	else return(part_2);
}

int main(int argc, char* argv[])
{
	//char *config_file = "C:\\Models_Interactions\\B_14_Join_csv\\itc_config.xml";
	//char *implementation_goals_file = "C:\\Models_Interactions\\implementation_goals.xml";

	char *config_file = argv[1];
	char *implementation_goals_file = argv[2];
	printf("\nINPUT CONFIG FILE: %s", config_file);
	std::vector<t_estimator_factor> v_factors, v_minimized_factors;
	std::vector<t_estimator_interaction> v_interactions, v_minimized_interactions;
	std::vector<t_response_variable> v_response_variables;
	std::vector<t_factor_desc> factor_descriptors;
	std::vector<string> full_factor_set;
	XMLDocument xmlDoc;
	std::vector<t_implementation_goal> v_implementation_goals;


	printf("\nFACTOR_VECTOR_SIZE: %i, sizeof cu_factor_estimator:%i\nINTERACTION_VECTOR_SIZE: %i, sizeof cu_interaction_estimator:%i", FACTOR_VECTOR_SIZE, sizeof(cu_factor_estimator), INTERACTION_VECTOR_SIZE, sizeof(cu_interaction_estimator));

	regex factor_expr("^\\s*([A-Za-z0-9_]+)[\\s,]+([-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?)");
	regex factor_name_expr("([A-Za-z0-9]+)");
	regex interaction_expr("^\\s*([A-Za-z0-9_]+)\\:([A-Za-z0-9_]+)[\\s,]+([-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?)");
	regex decimal_expr("([0-9]+)");
	regex intercept_expr("Intercept.*?[\\s,]+([-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?)");

	//Parse Configuration.xml
	XMLError eResult = xmlDoc.LoadFile(config_file);
	XMLCheckResult(eResult);
	XMLNode * pRoot = xmlDoc.FirstChild();
	if (pRoot == nullptr) printf("\nXML read error: %i", XML_ERROR_FILE_READ_ERROR);
	XMLElement * Xitem = pRoot->FirstChildElement("models")->FirstChildElement("responce_variable");
	string model_path = pRoot->FirstChildElement("models")->Attribute("path");
	int id = 0;
	while (Xitem != nullptr){
		//printf("\n%s", Xitem->Attribute("file"));
		struct t_response_variable c;
		c.id = id;
		c.name = Xitem->Attribute("name");
		c.model_filename = model_path + Xitem->Attribute("file");
		c.treshold = stof(Xitem->Attribute("value_treshold"));
		string dist = Xitem->Attribute("distribution");
		if (strcmp(dist.c_str(), "normal") == 0) c.dist = normal;
		else if (strcmp(dist.c_str(), "gamma") == 0) c.dist = gamma;
		else if (strcmp(dist.c_str(), "inverse gaussian") == 0) c.dist = inverse_gaussian;
		else if (strcmp(dist.c_str(), "poisson") == 0) c.dist = poisson;
		else c.dist = undefined;
		v_response_variables.push_back(c);
		Xitem = Xitem->NextSiblingElement("responce_variable");
		id++;
	}
	string fullfactorstring = pRoot->FirstChildElement("FactorialDesign")->Attribute("FullFactorSet");
	if (strcmp(fullfactorstring.c_str(), "") != 0){
		smatch match;
		while (regex_search(fullfactorstring, match, factor_name_expr)){
			full_factor_set.push_back(match[1]);
			fullfactorstring = match.suffix();
		}
	}

	//Parse Implementation_goals.xml
	eResult = xmlDoc.LoadFile(implementation_goals_file);
	XMLCheckResult(eResult);
	pRoot = xmlDoc.FirstChild();
	if (pRoot == nullptr) printf("\nXML read error: %i", XML_ERROR_FILE_READ_ERROR);
	Xitem = pRoot->FirstChildElement("goal");
	while (Xitem != nullptr){
		struct t_implementation_goal c;
		c.goal_name = Xitem->Attribute("name");
		XMLElement * V_item = Xitem->FirstChildElement("variable");
		c.valid_items_num = 0;
		while (V_item != nullptr){
			struct t_implementation_goal_item v;
			v.var_name = V_item->Attribute("name");
			v.weight = stof(V_item->Attribute("weight"));
			string buf = V_item->Attribute("goal");
			if (strcmp(buf.c_str(), "max") == 0) v.goal = v_max;
			else if (strcmp(buf.c_str(), "min") == 0) v.goal = v_min;
			else v.goal = v_undefined;
			c.items[c.valid_items_num] = v;
			c.valid_items_num += 1;
			V_item = V_item->NextSiblingElement("variable");
		}
		v_implementation_goals.push_back(c);
		Xitem = Xitem->NextSiblingElement("goal");
	}
	

	//1. Read regression model from file into v_factors and v_interactions
	std::string line;
	for (int i = 0; i<v_response_variables.size(); i++){
		std::ifstream rm_file(v_response_variables[i].model_filename);
		if (rm_file.is_open()){
			while (std::getline(rm_file, line)){
				try{
					smatch match;
					smatch idx_match;
					if (regex_search(line, match, intercept_expr) && match.size() > 1){
						v_response_variables[i].intercept = stof(match[1].str());
						printf("\nIntercept[%i]: %f", v_response_variables[i].id, v_response_variables[i].intercept);
					}
					else if (regex_search(line, match, factor_expr) && match.size() > 2){
						smatch local_match;
						struct t_estimator_factor c;
						c.factor = match[1].str();
						regex_search(c.factor, local_match, factor_name_expr);
						c.factor = local_match[1];
						c.value = stof(match[2].str());
						c.response_variable_id = v_response_variables[i].id;
						v_factors.push_back(c);
					}
					else if (regex_search(line, match, interaction_expr) && match.size() > 3){
						smatch local_match;
						struct t_estimator_interaction c;
						c.factor_1 = match[1].str();
						c.factor_2 = match[2].str();

						regex_search(c.factor_1, local_match, factor_name_expr);
						c.factor_1 = local_match[1];
						regex_search(c.factor_2, local_match, factor_name_expr);
						c.factor_2 = local_match[1];

						c.value = stof(match[3].str());
						c.response_variable_id = v_response_variables[i].id;
						v_interactions.push_back(c);
					}
				}
				catch (regex_error & e){
				}
			}
			rm_file.close();
		}
		else cout << "Unable to open file";
	}

	for (int i = 0; i < v_factors.size(); i++) printf("\nVarId: %i, Factor: %s, value = %g", v_factors[i].response_variable_id, v_factors[i].factor.c_str(), v_factors[i].value);
	for (int i = 0; i < v_interactions.size(); i++) printf("\nVarId: %i, Interaction: %s : %s, value = %g", v_interactions[i].response_variable_id, v_interactions[i].factor_1.c_str(), v_interactions[i].factor_2.c_str(), v_interactions[i].value);
	//Minimize model (remove factors/interaction with impact smaller than treshold (to speed-up computations)
	for (int i = 0; i < v_factors.size(); i++){
		if (fabs(v_factors[i].value) >= v_response_variables[v_factors[i].response_variable_id].treshold) v_minimized_factors.push_back(v_factors[i]);
	}
	for (int i = 0; i < v_interactions.size(); i++){
		if (fabs(v_interactions[i].value) >= v_response_variables[v_interactions[i].response_variable_id].treshold) v_minimized_interactions.push_back(v_interactions[i]);
	}
	printf("\n\n\t\tMINIMIZED MODEL:\n\n");
	for (int i = 0; i < v_minimized_factors.size(); i++) printf("\nVarId: %i, Factor: %s, value = %g", v_minimized_factors[i].response_variable_id, v_minimized_factors[i].factor.c_str(), v_minimized_factors[i].value);
	for (int i = 0; i < v_minimized_interactions.size(); i++) printf("\nVarId: %i, Interaction: %s : %s, value = %g", v_minimized_interactions[i].response_variable_id, v_minimized_interactions[i].factor_1.c_str(), v_minimized_interactions[i].factor_2.c_str(), v_minimized_interactions[i].value);

	for (int i = 0; i < v_minimized_factors.size(); i++){
		if (get_index(factor_descriptors, v_minimized_factors[i].factor) < 0){
			struct t_factor_desc c = { v_minimized_factors[i].factor, 0 };
			factor_descriptors.push_back(c);
		}
	};
	for (int i = 0; i < v_minimized_interactions.size(); i++){
		if (get_index(factor_descriptors, v_minimized_interactions[i].factor_1) < 0){
			struct t_factor_desc c = { v_minimized_interactions[i].factor_1, 0 };
			factor_descriptors.push_back(c);
		}
		if (get_index(factor_descriptors, v_minimized_interactions[i].factor_2) < 0){
			struct t_factor_desc c = { v_minimized_interactions[i].factor_2, 0 };
			factor_descriptors.push_back(c);
		}
	};
	sort(factor_descriptors.begin(), factor_descriptors.end(), compare_by_name);
	for (int i = 0; i < factor_descriptors.size(); i++)factor_descriptors[i].id = i;

	for (int i = 0; i < v_minimized_factors.size(); i++){
		int idx = get_id(factor_descriptors, v_minimized_factors[i].factor);
		if (idx >= 0) v_minimized_factors[i].id = idx;
		else  printf("\nERROR: Index not found for factor: %s", v_minimized_factors[i].factor);
	};
	for (int i = 0; i < v_minimized_interactions.size(); i++){
		int idx_1 = get_id(factor_descriptors, v_minimized_interactions[i].factor_1);
		int idx_2 = get_id(factor_descriptors, v_minimized_interactions[i].factor_2);
		if (idx_1 >= 0 && idx_2 >= 0){ v_minimized_interactions[i].id_1 = idx_1; v_minimized_interactions[i].id_2 = idx_2; }
		else  printf("\nERROR: Index not found for interaction: %s : %s", v_minimized_interactions[i].factor_1, v_minimized_interactions[i].factor_2);
	};
	for (int i = 0; i < factor_descriptors.size(); i++)printf("\n\tFactor ID: %i, Name: %s", factor_descriptors[i].id, factor_descriptors[i].name.c_str());


	//********** MEMORY ALLOCATION ******************//
	host_factor_vector = (cu_factor_estimator*)malloc(sizeof(cu_factor_estimator)* FACTOR_VECTOR_SIZE);
	host_interaction_vector = (cu_interaction_estimator*)malloc(sizeof(cu_interaction_estimator)* INTERACTION_VECTOR_SIZE);
	host_response_variables = (cu_response_variable*)malloc(sizeof(cu_response_variable)* MAX_MODELS);
	host_data_descriptor = { v_response_variables.size(), v_minimized_factors.size(), v_minimized_interactions.size(), factor_descriptors.size() };
	host_job_descriptor = { uint64_t(1) << (factor_descriptors.size()), (uint64_t(1) << (factor_descriptors.size())) / uint64_t(CU_RESULT_LEN) };
	if (host_job_descriptor.points_per_thread < 1){
		host_job_descriptor.points_per_thread = 1;
	}
	else if (host_job_descriptor.points_per_thread > MAX_POINTS_PER_THREAD){
		host_job_descriptor.points_per_thread = MAX_POINTS_PER_THREAD;
	}


	for (int i = 0; i < host_data_descriptor.real_factor_estimators; i++){
		host_factor_vector[i].id = v_minimized_factors[i].id;
		host_factor_vector[i].response_variable_id = v_minimized_factors[i].response_variable_id;
		host_factor_vector[i].value = v_minimized_factors[i].value;
	};
	for (int i = 0; i < host_data_descriptor.real_interaction_estimators; i++){
		host_interaction_vector[i].id_1 = v_minimized_interactions[i].id_1;
		host_interaction_vector[i].id_2 = v_minimized_interactions[i].id_2;
		host_interaction_vector[i].response_variable_id = v_minimized_interactions[i].response_variable_id;
		host_interaction_vector[i].value = v_minimized_interactions[i].value;
	};
	for (int i = 0; i < host_data_descriptor.real_models; i++){
		host_response_variables[i].factor_first = 0;
		host_response_variables[i].interaction_first = 0;
		host_response_variables[i].id = v_response_variables[i].id;
		host_response_variables[i].intercept = v_response_variables[i].intercept;
		host_response_variables[i].dist = v_response_variables[i].dist;
		//factors
		for (int j = 0; j < host_data_descriptor.real_factor_estimators; j++){
			if (host_factor_vector[j].response_variable_id == host_response_variables[i].id){
				host_response_variables[i].factor_first = j;
				break;
			}
		};
		int len = 0;
		for (int j = host_response_variables[i].factor_first; j < host_data_descriptor.real_factor_estimators; j++){
			if (host_factor_vector[j].response_variable_id != host_response_variables[i].id){
				len = j - host_response_variables[i].factor_first;
				break;
			}
		};
		if (len == 0){
			if (host_response_variables[i].factor_first == 0 && host_response_variables[i].id != 0)len = 0;
			else len = host_data_descriptor.real_factor_estimators - host_response_variables[i].factor_first;
		}
		host_response_variables[i].factor_num = len;
		//interactions
		for (int j = 0; j < host_data_descriptor.real_interaction_estimators; j++){
			if (host_interaction_vector[j].response_variable_id == host_response_variables[i].id){
				host_response_variables[i].interaction_first = j;
				break;
			}
		};
		len = 0;
		for (int j = host_response_variables[i].interaction_first; j < host_data_descriptor.real_interaction_estimators; j++){
			if (host_interaction_vector[j].response_variable_id != host_response_variables[i].id){
				len = j - host_response_variables[i].interaction_first;
				break;
			}
		};
		if (len == 0){ 
			if (host_response_variables[i].interaction_first == 0 && host_response_variables[i].id!=0) len = 0;
			else len = host_data_descriptor.real_interaction_estimators - host_response_variables[i].interaction_first;
		}
		host_response_variables[i].interaction_num = len;
	};

	for (int i = 0; i < host_data_descriptor.real_models; i++){
		printf("\n\nmodel [%i], factor_first [%i], factor_len [%i], interaction_first [%i], interaction_len [%i], intercept [%g]", host_response_variables[i].id, host_response_variables[i].factor_first, host_response_variables[i].factor_num, host_response_variables[i].interaction_first, host_response_variables[i].interaction_num, host_response_variables[i].intercept);
	}

	//link variables in implementation goals to the models by variable id
	for (int i = 0; i < v_implementation_goals.size(); i++){
		for (int j = 0; j < v_implementation_goals[i].valid_items_num; j++){
			for (int c = 0; c < v_response_variables.size(); c++){
				if (v_implementation_goals[i].items[j].var_name == v_response_variables[c].name){
					v_implementation_goals[i].items[j].var_id = v_response_variables[c].id;
				}
			}
		}
	}


	dummy_wakeup_const_memory();
	HANDLE_ERROR(cudaMemcpyToSymbol(cuda_factor_vector, host_factor_vector, sizeof(cu_factor_estimator)* FACTOR_VECTOR_SIZE));
	HANDLE_ERROR(cudaMemcpyToSymbol(cuda_interaction_vector, host_interaction_vector, sizeof(cu_interaction_estimator)* INTERACTION_VECTOR_SIZE));
	HANDLE_ERROR(cudaMemcpyToSymbol(cuda_response_variables, host_response_variables, sizeof(cu_response_variable)* MAX_MODELS,0,cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpyToSymbol(cuda_data_descriptor, &host_data_descriptor, sizeof(input_data_desctiptor)));
	HANDLE_ERROR(cudaMemcpyToSymbol(cuda_jobdesc, &host_job_descriptor, sizeof(cu_job_descriptor)));

	//MCDM STARTS HERE
	string summary_file_name = model_path + "MCDM_summary.xml";
	FILE* fp = std::fopen(summary_file_name.c_str(), "w");
	fprintf(fp, "<Summary \n\tJoined_Factor_Set=\"");
	for (int i = 0; i < factor_descriptors.size(); i++)fprintf(fp, "%s,", factor_descriptors[i].name.c_str()); 
	fprintf(fp, "\"\n\tFull_Factor_Set=\"");
	for (int i = 0; i < full_factor_set.size(); i++)fprintf(fp, "%s,", full_factor_set[i].c_str());
	fprintf(fp, "\"\n\t>");

	for (int i = 0; i < host_data_descriptor.real_models; i++){
		printf("\n\n");
		int m = host_response_variables[i].id;
		//cu_thread_result freq = compute_min_max_on_host(i);
		cu_thread_result minmax = compute_min_max_on_cuda(m);
		host_response_variables[m].max = (minmax.max > v_response_variables[m].treshold) ? minmax.max : 0;
		host_response_variables[m].min = (minmax.min > v_response_variables[m].treshold) ? minmax.min : 0;
		//string config_min = get_configvector_csv(factor_descriptors, minmax.min_index);
		//string config_max = get_configvector_csv(factor_descriptors, minmax.max_index);
		//string config_min = get_fullconfigvector_csv(full_factor_set, factor_descriptors, minmax.min_index);
		//string config_max = get_fullconfigvector_csv(full_factor_set, factor_descriptors, minmax.max_index);
		string config_min = get_fullconfigvector_varid_specific_csv(full_factor_set, v_minimized_factors, m, minmax.min_index, false);
		string config_max = get_fullconfigvector_varid_specific_csv(full_factor_set, v_minimized_factors, m, minmax.max_index, false);

		fprintf(fp, "\n\n\t<Model\n\t\tName = \"%s\"\n\t\tMin_Val= \"%.2f\"\n\t\tMax_Val= \"%.2f\"", v_response_variables[m].name.c_str(), host_response_variables[m].min, host_response_variables[m].max);
		fprintf(fp, "\n\t\tConfig_Min=\"%s\"\n\t\tConfig_Max=\"%s\"\n\t/>", config_min.c_str(), config_max.c_str());
		cout << "\nModel[" << m << "] = " << v_response_variables[m].name << "\n\tmin_val= " << host_response_variables[m].min << " (conf: " << minmax.min_index << "),\n\tmax_val= " << host_response_variables[m].max << " (conf: " << minmax.max_index << ")";
		//cout << "\nConfig Min:\n" << config_min << "\nConfig Max:\n" << config_max;
	};
	HANDLE_ERROR(cudaMemcpyToSymbol(cuda_response_variables, host_response_variables, sizeof(cu_response_variable)* MAX_MODELS, 0, cudaMemcpyHostToDevice));
	printf("\n\n");




	//Process implementation goals
	host_implementation_goal = (cu_implementation_goal_item*)malloc(sizeof(cu_implementation_goal_item)*MAX_MODELS);
	for (int i = 0; i<v_implementation_goals.size(); i++){
		int valid_items_num = v_implementation_goals[i].valid_items_num;
		for (int j = 0; j<valid_items_num; j++){
			host_implementation_goal[j].goal = v_implementation_goals[i].items[j].goal;
			host_implementation_goal[j].var_id = v_implementation_goals[i].items[j].var_id;
			host_implementation_goal[j].weight = v_implementation_goals[i].items[j].weight;
		};
		HANDLE_ERROR(cudaMemcpyToSymbol(cuda_implementation_goal, host_implementation_goal, sizeof(cu_implementation_goal_item)*MAX_MODELS));
		printf("\n\nProcess Implementation goal: %s", v_implementation_goals[i].goal_name.c_str());
		cu_thread_result minmax = process_implementation_goal_on_cuda(valid_items_num);
		
		std::vector<t_factor_desc> significant_factors;
		for (int j = 0; j < valid_items_num; j++){
			if (v_implementation_goals[i].items[j].weight > 0){
				int var_id = v_implementation_goals[i].items[j].var_id;
				//single factors
				for (int x = 0; x < v_minimized_factors.size(); x++){
					if (v_minimized_factors[x].response_variable_id == var_id){
						int tx = get_index(factor_descriptors, v_minimized_factors[x].factor);
						if (get_index(significant_factors, v_minimized_factors[x].factor) < 0){
							significant_factors.push_back(factor_descriptors[tx]);
						}
					}
				}
				//interactions
				for (int x = 0; x < v_minimized_interactions.size(); x++){
					if (v_minimized_interactions[x].response_variable_id == var_id){
						int tx1 = get_index(factor_descriptors, v_minimized_interactions[x].factor_1);
						int tx2 = get_index(factor_descriptors, v_minimized_interactions[x].factor_2);
						if (get_index(significant_factors, v_minimized_interactions[x].factor_1) < 0){
							significant_factors.push_back(factor_descriptors[tx1]);
						}
						if (get_index(significant_factors, v_minimized_interactions[x].factor_2) < 0){
							significant_factors.push_back(factor_descriptors[tx2]);
						}
					}
				}
			}
		}
		sort(significant_factors.begin(), significant_factors.end(), compare_by_name);


		string config_min = get_fullconfigvector_significant_only_csv(full_factor_set, factor_descriptors, significant_factors, minmax.min_index, false);
		string config_max = get_fullconfigvector_significant_only_csv(full_factor_set, factor_descriptors, significant_factors, minmax.max_index, false);
		cout << "\n\t\tMin_score: " << minmax.min << " (conf: " << minmax.min_index << ")\n\t\tMax_score: " << minmax.max << " (conf: " << minmax.max_index << ")";

		//fprintf(fp, "\n\n\t<Goal \n\t\tname = \"%s\"\n\t\tBest_Score = \"%.5f\"\n\t\tWorst_Score = \"%.5f\"\n\t\tBest_Config =  \"%s\"\n\t\tWorst_Config = \"%s\"\n\t>", v_implementation_goals[i].goal_name.c_str(), minmax.max, minmax.min, config_max.c_str(), config_min.c_str());
		fprintf(fp, "\n\n\t<Goal name = \"%s\">", v_implementation_goals[i].goal_name.c_str());
		fprintf(fp, "\n\t\t<Best\n\t\t\tScore = \"%.2f\"\n\t\t\tConfig = \"%s\"\n\t\t>", minmax.max, config_max.c_str());
		for (int j = 0; j < valid_items_num; j++){
			float val = get_varvalue(v_implementation_goals[i].items[j].var_id, minmax.max_index);
			fprintf(fp, "\n\t\t\t<Variable name = \"%s\" value = \"%.2f\"/>", v_implementation_goals[i].items[j].var_name.c_str(), val);
		}
		fprintf(fp, "\n\t\t</Best>\n\t\t<Worst\n\t\t\tScore = \"%.2f\"\n\t\t\tConfig = \"%s\"\n\t\t>", minmax.min, config_min.c_str());
		for (int j = 0; j < valid_items_num; j++){
			float val = get_varvalue(v_implementation_goals[i].items[j].var_id, minmax.min_index);
			fprintf(fp, "\n\t\t\t<Variable name = \"%s\" value = \"%.2f\"/>", v_implementation_goals[i].items[j].var_name.c_str(), val);
		}

		fprintf(fp,"\n\t\t</Worst>\n\t</Goal>");
	}

	fprintf(fp, "\n\n</Summary>\n");
	fclose(fp);
	return 0;
}

