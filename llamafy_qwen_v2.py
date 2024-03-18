# coding=utf-8
# Converts the 2nd version of the Qwen models in the same format as LLaMA2.
# Usage: python llamafy_qwen_v2.py --input_dir Qwen1.5-0.5B-Chat --output_dir Qwen1.5-0.5B-Chat_llamafy
# Converted model: https://github.com/Minami-su/character_AI_open/blob/main/llamafy_qwen_v2.py

import json
import os
from collections import OrderedDict
from typing import Any, Dict, Optional

import fire
import torch
from safetensors import safe_open
from safetensors.torch import save_file
from tqdm import tqdm
from transformers.modeling_utils import (
    SAFE_WEIGHTS_INDEX_NAME,
    SAFE_WEIGHTS_NAME,
    WEIGHTS_INDEX_NAME,
    WEIGHTS_NAME,
    shard_checkpoint,
)
from transformers.utils import check_min_version

try:
    check_min_version("4.34.0")
except Exception:
    raise ValueError("Please upgrade `transformers` to 4.34.0")

CONFIG_NAME = "config.json"


def save_weight(input_dir: str, output_dir: str, shard_size: str, save_safetensors: bool) -> str:
    qwen_state_dict: Dict[str, torch.Tensor] = OrderedDict()
    for filepath in tqdm(os.listdir(input_dir), desc="Load weights"):
        if os.path.isfile(os.path.join(input_dir, filepath)) and filepath.endswith(".safetensors"):
            with safe_open(os.path.join(input_dir, filepath), framework="pt", device="cpu") as f:
                for key in f.keys():
                    qwen_state_dict[key] = f.get_tensor(key)

    llama2_state_dict: Dict[str, torch.Tensor] = OrderedDict()
    torch_dtype = None
    for key, value in tqdm(qwen_state_dict.items(), desc="Convert format"):
        if torch_dtype is None:
            torch_dtype = value.dtype
        if "self_attn.o_proj" in key:
            #print(key)
            llama2_state_dict[key] = value
            llama2_state_dict[key.replace(".weight",".bias")] = torch.zeros_like(
                    value[:, 0]
                ).squeeze()
        else:
            llama2_state_dict[key] = value

    weights_name = SAFE_WEIGHTS_NAME if save_safetensors else WEIGHTS_NAME
    shards, index = shard_checkpoint(llama2_state_dict, max_shard_size=shard_size, weights_name=weights_name)

    for shard_file, shard in tqdm(shards.items(), desc="Save weights"):
        if save_safetensors:
            save_file(shard, os.path.join(output_dir, shard_file), metadata={"format": "pt"})
        else:
            torch.save(shard, os.path.join(output_dir, shard_file))

    if index is None:
        print("Model weights saved in {}".format(os.path.join(output_dir, weights_name)))
    else:
        index_name = SAFE_WEIGHTS_INDEX_NAME if save_safetensors else WEIGHTS_INDEX_NAME
        with open(os.path.join(output_dir, index_name), "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, sort_keys=True)
        print("Model weights saved in {}".format(output_dir))

    return str(torch_dtype).replace("torch.", "")


def save_config(input_dir: str, output_dir: str, torch_dtype: str):
    with open(os.path.join(input_dir, CONFIG_NAME), "r", encoding="utf-8") as f:
        qwen_config_dict: Dict[str, Any] = json.load(f)

    llama2_config_dict: Dict[str, Any] = OrderedDict()
    llama2_config_dict["architectures"] = ["LlamaForCausalLM"]
    llama2_config_dict["attention_bias"] = True
    llama2_config_dict["attention_dropout"] = qwen_config_dict["attention_dropout"]
    llama2_config_dict["hidden_act"] = "silu"
    llama2_config_dict["hidden_size"] = qwen_config_dict["hidden_size"]
    llama2_config_dict["initializer_range"] = qwen_config_dict["initializer_range"]
    llama2_config_dict["intermediate_size"] = qwen_config_dict["intermediate_size"]
   #llama2_config_dict["max_position_embeddings"] = qwen_config_dict["max_position_embeddings"]
    llama2_config_dict["max_position_embeddings"] = 4096
    llama2_config_dict["max_window_layers"] = qwen_config_dict["max_window_layers"]
    llama2_config_dict["model_type"] = "llama"
    llama2_config_dict["num_attention_heads"] = qwen_config_dict["num_attention_heads"]
    llama2_config_dict["num_hidden_layers"] = qwen_config_dict["num_hidden_layers"]
    llama2_config_dict["num_key_value_heads"] = qwen_config_dict["num_key_value_heads"]
    llama2_config_dict["pretraining_tp"] = 1
    llama2_config_dict["rms_norm_eps"] = qwen_config_dict["rms_norm_eps"]
    llama2_config_dict["rope_theta"] = qwen_config_dict["rope_theta"]
    llama2_config_dict["rope_scaling"] = None
    llama2_config_dict["sliding_window"]=qwen_config_dict["sliding_window"]
    llama2_config_dict["tie_word_embeddings"] = qwen_config_dict["tie_word_embeddings"]
    llama2_config_dict["torch_dtype"] = torch_dtype
    llama2_config_dict["transformers_version"] = "4.37.0"
    llama2_config_dict["use_cache"] = True
    llama2_config_dict["use_sliding_window"] = qwen_config_dict["use_sliding_window"]
    llama2_config_dict["vocab_size"] = qwen_config_dict["vocab_size"]


    with open(os.path.join(output_dir, CONFIG_NAME), "w", encoding="utf-8") as f:
        json.dump(llama2_config_dict, f, indent=2)
    print("Model config saved in {}".format(os.path.join(output_dir, CONFIG_NAME)))


def llamafy_qwen_v2(
        input_dir: str, output_dir: str, shard_size: Optional[str] = "2GB", save_safetensors: Optional[bool] = False
):
    try:
        os.makedirs(output_dir, exist_ok=False)
    except Exception as e:
        raise print("Output dir already exists", e)

    torch_dtype = save_weight(input_dir, output_dir, shard_size, save_safetensors)
    save_config(input_dir, output_dir, torch_dtype)


if __name__ == "__main__":
    fire.Fire(llamafy_qwen_v2)
