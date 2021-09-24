"""General utilities."""
import collections
import json
import logging
import os
import random

import numpy as np
import torch
from transformers import (
    AutoConfig,
    AutoTokenizer,
    AutoModelForMaskedLM,
)


logger = logging.getLogger(__name__)


def set_seed(seed: int):
    """Sets the relevant random seeds."""
    random.seed(seed)
    np.random.seed(seed)
    torch.random.manual_seed(seed)
    torch.cuda.manual_seed(seed)


def check_args(args):
    """Checks for invalid argument combinations."""
    if args['evaluation_strategy'] == 'exact-match':
        assert args['decoding_strategy'] is not None
    if args['evaluation_strategy'] == 'classification':
        assert args['label_map'] is not None
    if args['evaluation_strategy'] == 'multiple-choice':
        assert args['bsz'] is None, 'Multiple choice uses custom batching, do not set `--bsz`.'
    if args.get('l1decay', 0.0) != 0.0:
        assert args['linear'], 'L1 regularization only applies to linear combo mlms.'
        assert args['l1decay'] > 0.0, 'L1 decay cannot be negative.'


def serialize_args(args):
    """Serializes arguments to the checkpoint directory."""
    if not os.path.exists(args['ckpt_dir']):
        logger.info(f'Making directory: {args["ckpt_dir"]}')
        os.makedirs(args['ckpt_dir'])
    fname = os.path.join(args['ckpt_dir'], 'args.json')
    with open(fname, 'w') as f:
        logger.info(f'Serializing CLI arguments to: {fname}')
        json.dump(args, f)


def load_label_map(label_map):
    """Loads the label map."""
    if label_map is not None:
        return json.loads(label_map)
    return None


def randomize_label_map(label_map, tokenizer):
    while True:
        new_ids = torch.randint(
            low=1000,  # To avoid special tokens
            high=len(tokenizer),
            size=(len(label_map),)
        )
        new_tokens = [tokenizer.decode(idx) for idx in new_ids]
        lens = [len(tokenizer.encode(tok, add_special_tokens=False)) for tok in new_tokens]
        # Continue choosing random tokens until they are all unique and will not be split into
        # multiple tokens.
        if all(l == 1 for l in lens) and len(set(new_tokens)) == len(new_tokens):
            break
    out = {k: v for k, v in zip(label_map.keys(), new_tokens)}
    return out


def load_transformers(model_name, skip_model=False):
    """Loads transformers config, tokenizer, and model."""
    config = AutoConfig.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        add_prefix_space=True,
        additional_special_tokens=('[T]', '[P]'),
    )
    model = AutoModelForMaskedLM.from_pretrained(model_name, config=config)
    return config, tokenizer, model


def get_initial_trigger_ids(initial_trigger, tokenizer):
    """Converts a list of trigger tokens to a tensor of trigger token ids."""
    if not initial_trigger:
        return None
    initial_trigger_ids = torch.tensor(
        tokenizer.convert_tokens_to_ids(initial_trigger)
    )
    detokenized = tokenizer.convert_ids_to_tokens(initial_trigger_ids)
    logger.debug(f'Initial trigger (detokenized): {detokenized}')
    return initial_trigger_ids


def to_device(data, device):
    """Places all tensors in data on the given device."""
    if isinstance(data, dict):
        return {k: to_device(v, device) for k, v in data.items()}
    if isinstance(data, list):
        return [to_device(x, device) for x in data]
    if isinstance(data, torch.Tensor):
        return data.to(device)
    raise ValueError(
        'Could not place on device: `data` should be a tensor or dictionary/list '
        'containing tensors.'
    )


# TODO(rloganiv): Probably want to make a proper interface for metrics instead of taking this janky
# approach.
def update_metrics(total_metrics, metrics):
    """
    Updates total metrics w/ metrics for a batch.

    WARNING: This mutates the metrics dict.
    """
    for metric in metrics:
        if metric in total_metrics:
            total_metrics[metric] += metrics[metric].detach()
        else:
            total_metrics[metric] = metrics[metric].detach()


class NullWriter:
    def add_scalar(self, *args, **kwargs):
        return


DistributedConfig = collections.namedtuple(
    'DistributedConfig',
    ['device', 'local_rank', 'world_size', 'is_main_process'],
)


def distributed_setup(local_rank):
    """Sets up distributed training."""
    world_size = os.getenv('WORLD_SIZE')
    if world_size is None:
        world_size = -1
    if local_rank == -1:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device('cuda', local_rank)
        if world_size != -1:
            torch.distributed.init_process_group(
                backend='nccl',
                init_method='env://',
                rank=local_rank,
                world_size=world_size,
            )
    is_main_process = local_rank in [-1, 0] or world_size == -1
    logger.info('Rank: %s - World Size: %s', local_rank, world_size)
    return DistributedConfig(device, local_rank, world_size, is_main_process)
