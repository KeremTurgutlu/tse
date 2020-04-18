# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02-tokenizers.ipynb (unless otherwise specified).

__all__ = ['squad_processor', 'get_squad_dataset', 'MAX_SEQ_LEN', 'MAX_QUERY_LEN', 'DOC_STRIDE',
           'find_best_start_end_idxs', 'answer_from_orig_context']

# Cell
from fastai.core import *
from transformers import AutoModel, AutoTokenizer, RobertaTokenizer
import tokenizers

# Cell
from transformers.data.processors.squad import SquadV2Processor, squad_convert_examples_to_features

# Cell
squad_processor = SquadV2Processor()

# Cell
MAX_SEQ_LEN = 104
MAX_QUERY_LEN = 5
DOC_STRIDE = 200 # useful for LM modeling
def get_squad_dataset(examples, tokenizer, is_training):
    return squad_convert_examples_to_features(
        examples=examples,
        tokenizer=tokenizer,
        doc_stride=DOC_STRIDE,
        max_seq_length=MAX_SEQ_LEN,
        max_query_length=MAX_QUERY_LEN,
        is_training=is_training,
        return_dataset="pt",
        threads=defaults.cpus,
    )

# Cell
def find_best_start_end_idxs(_start_logits, _end_logits):
    best_logit = -1e6
    best_idxs = None
    for start_idx, start_logit in enumerate(_start_logits):
        for end_idx, end_logit in enumerate(_end_logits[start_idx:]):
            logit_sum = (start_logit + end_logit).item()
            if logit_sum > best_logit:
                best_logit = logit_sum
                best_idxs = (start_idx, start_idx+end_idx)
    return best_idxs

# Cell
def answer_from_orig_context(context, char_to_offset, tok_orig_char_start, tok_orig_char_end):
    """
    Find answer segment char by char from context in
    example.context and example.char_to_word_offset
    """
    answer_chars = [char for char, offs_id in zip(context, char_to_offset)
                if (offs_id >= tok_orig_char_start) & (offs_id <= tok_orig_char_end)]
    predicted_answer = "".join(answer_chars).strip()
    return predicted_answer