# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04-models.ipynb (unless otherwise specified).

__all__ = ['get_roberta_model', 'do_tfms', 'QAHead', 'TSEModel', 'CELoss', 'LSLoss', 'jaccard',
           'get_best_start_end_idxs', 'JaccardScore', 'model_split_func']

# Cell
from fastai.text import *
from transformers import RobertaModel, RobertaConfig
from .tokenizers import *
from .datasets import *

# Cell
def get_roberta_model(path_to_dir="../roberta-base/"):
    conf = RobertaConfig.from_pretrained(path_to_dir)
    conf.output_hidden_states = True
    model = RobertaModel.from_pretrained(path_to_dir, config=conf)
    # outputs: (final_hidden, pooled_final_hidden, (embedding + 12 hidden))
    return model

# Cell
do_tfms = {}
do_tfms["random_left_truncate"] = {"p":.3}
do_tfms["random_right_truncate"] = {"p":.3}
do_tfms["random_replace_with_mask"] = {"p":.3, "mask_p":0.2}
do_tfms

# Cell
class QAHead(Module):
    def __init__(self, p=0.5):
        self.d0 = nn.Dropout(p)
        self.l0 = nn.Linear(768*2, 2)
    def forward(self, x):
        return self.l0(self.d0(x))

class TSEModel(Module):
    def __init__(self, model):
        self.sequence_model = model
        self.head = QAHead()

    def forward(self, *xargs):
        inp = {}
        inp["input_ids"] = xargs[0]
        inp["attention_mask"] = xargs[1]
        _, _, hidden_states = self.sequence_model(**inp)
        x = torch.cat([hidden_states[-1], hidden_states[-1]], dim=-1)
        start_logits, end_logits = self.head(x).split(1, dim=-1)
        return (start_logits.squeeze(-1), end_logits.squeeze(-1))

# Cell
class CELoss(Module):
    "single backward by concatenating both start and logits with correct targets"
    def __init__(self): self.loss_fn = nn.CrossEntropyLoss()
    def forward(self, inputs, start_targets, end_targets):
        start_logits, end_logits = inputs
        logits = torch.cat([start_logits, end_logits]).contiguous()
        targets = torch.cat([start_targets, end_targets]).contiguous()
        return self.loss_fn(logits, targets)

# Cell
class LSLoss(Module):
    "single backward by concatenating both start and logits with correct targets"
    def __init__(self, eps=0.1): self.loss_fn = LabelSmoothingCrossEntropy(eps=eps)
    def forward(self, inputs, start_targets, end_targets):
        start_logits, end_logits = inputs
        logits = torch.cat([start_logits, end_logits]).contiguous()
        targets = torch.cat([start_targets, end_targets]).contiguous()
        return self.loss_fn(logits, targets)

# Cell
def jaccard(str1, str2):
    a = set(str1.lower().split())
    b = set(str2.lower().split())
    c = a.intersection(b)
    return float(len(c)) / (len(a) + len(b) - len(c))

# Cell
def get_best_start_end_idxs(_start_logits, _end_logits):
    best_logit = -1000
    best_idxs = None
    for start_idx, start_logit in enumerate(_start_logits):
        for end_idx, end_logit in enumerate(_end_logits[start_idx:]):
            logit_sum = (start_logit + end_logit).item()
            if logit_sum > best_logit:
                best_logit = logit_sum
                best_idxs = (start_idx, start_idx+end_idx)
    return best_idxs

# Cell
class JaccardScore(Callback):
    "Stores predictions and targets to perform calculations on epoch end."
    def __init__(self, valid_ds):
        self.valid_ds = valid_ds
        self.offset_shift = 4


    def on_epoch_begin(self, **kwargs):
        self.jaccard_scores = []
        self.valid_ds_idx = 0


    def on_batch_end(self, last_input:Tensor, last_output:Tensor, last_target:Tensor, **kwargs):

        input_ids, attention_masks = last_input[0], last_input[1].bool()
        start_logits, end_logits = last_output


        # mask select only context part
        for i in range(len(input_ids)):

            _input_ids = input_ids[i].masked_select(attention_masks[i])
            _start_logits = start_logits[i].masked_select(attention_masks[i])[4:-1]
            _end_logits = end_logits[i].masked_select(attention_masks[i])[4:-1]
            start_idx, end_idx = get_best_start_end_idxs(_start_logits, _end_logits)
            start_idx, end_idx = start_idx + self.offset_shift, end_idx + self.offset_shift

            context_text = self.valid_ds.inputs[self.valid_ds_idx]['context_text']
            offsets = self.valid_ds.inputs[self.valid_ds_idx]['offsets']
            answer_text = self.valid_ds.inputs[self.valid_ds_idx]['answer_text']

            start_offs, end_offs = offsets[start_idx], offsets[end_idx]
            answer = context_text[start_offs[0]:end_offs[1]]

            self.jaccard_scores.append(jaccard(answer, answer_text))
            self.valid_ds_idx += 1

    def on_epoch_end(self, last_metrics, **kwargs):
        res = np.mean(self.jaccard_scores)
        return add_metrics(last_metrics, res)

# Cell
def model_split_func(m):
    "4 layer groups"
    n = (2*len(m.sequence_model.encoder.layer))//3
    return (m.sequence_model.embeddings,
            m.sequence_model.encoder.layer[:n],
            m.sequence_model.encoder.layer[n:],
            m.head)