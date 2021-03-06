# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02-tokenizers.ipynb (unless otherwise specified).

__all__ = ['init_roberta_tokenizer']

# Cell
import tokenizers; print(f"tokenizers: {tokenizers.__version__}")
import fastai; print(f"fastai: {fastai.__version__}")
from fastai.text import *

from .preprocessing import *

# Cell
from tokenizers import Tokenizer, AddedToken, pre_tokenizers, decoders, processors
from tokenizers.models import BPE
from tokenizers.normalizers import BertNormalizer, Lowercase

def init_roberta_tokenizer(vocab_file, merges_file, max_length=192, do_lower_case=True):
    roberta = Tokenizer(BPE(vocab_file, merges_file))
    if do_lower_case: roberta.normalizer = Lowercase()
    roberta.pre_tokenizer = pre_tokenizers.ByteLevel()
    roberta.decoder = decoders.ByteLevel()

    roberta.enable_padding(pad_id=roberta.token_to_id("<pad>"),
                           pad_token="<pad>",
                           max_length=max_length)

    roberta.enable_truncation(max_length=max_length, strategy="only_second")

    roberta.add_special_tokens([
        AddedToken("<mask>", lstrip=True),
        "<s>",
        "</s>"
    ])

    roberta.post_processor = processors.RobertaProcessing(
        ("</s>", roberta.token_to_id("</s>")),
        ("<s>", roberta.token_to_id("<s>")),
    )

    roberta.pad_token_id = roberta.token_to_id("<pad>")
    roberta.eos_token_id = roberta.token_to_id("</s>")
    roberta.bos_token_id = roberta.token_to_id("<s>")
    roberta.unk_token_id = roberta.token_to_id("<unk>")
    roberta.mask_token_id = roberta.token_to_id("<mask>")
    return roberta