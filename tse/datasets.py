# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03-datasets.ipynb (unless otherwise specified).

__all__ = ['get_start_end_idxs', 'get_start_end_tok_idxs', 'QAInputGenerator', 'TSEDataAugmentor', 'do_tfms',
           'TSEDataset']

# Cell
from fastai.text import *
from .preprocessing import *
from .tokenizers import *

# Cell
def get_start_end_idxs(context, answer):
    "Get string start and end char for answer span"
    len_a = len(answer)
    for i, _ in enumerate(context):
        if context[i:i+len_a] == answer:
            start_idx, end_idx = i, i+len_a-1
            return start_idx, end_idx
    raise Exception("No overlapping segment found")

# Cell
def get_start_end_tok_idxs(offsets, start_idx, end_idx):
    "Generate target from tokens - first 4 tokens belong to question"
    start_tok_idx, end_tok_idx = None, None
    for tok_idx, off in enumerate(offsets[4:]):
        if (off[0] <= start_idx) & (off[1] > start_idx): start_tok_idx = tok_idx + 4
        if (off[0] <= end_idx) & (off[1] > end_idx): end_tok_idx = tok_idx + 4
    return (start_tok_idx, end_tok_idx)

# Cell
class QAInputGenerator:
    def __init__(self, contexts, questions, text_ids=None, answers=None, tokenizer=None):
        self.contexts, self.questions, self.answers = contexts, questions, answers
        self.outputs = tokenizer.encode_batch(list(tuple(zip(questions, contexts))))
        if text_ids is not None: self.text_ids = text_ids
        if self.answers is not None:
            self.start_end_idxs = [get_start_end_idxs(s1,s2) for (s1,s2) in zip(self.contexts, self.answers)]


    @classmethod
    def from_df(cls, df,
                ctx_col='text', q_col='sentiment', id_col='textID', ans_col='selected_text',
                is_test=False, tokenizer=None):
        contexts = df[ctx_col].values
        questions = df[q_col].values
        text_ids = None if id_col is None else df[id_col].values
        answers = None if is_test else df[ans_col].values
        return cls(contexts, questions, text_ids, answers, tokenizer)


    def __getitem__(self, i):

        input_ids = array(self.outputs[i].ids)
        attention_mask = array(self.outputs[i].attention_mask)
        offsets = array(self.outputs[i].offsets)
        tokens = array(self.outputs[i].tokens)
        res = {"input_ids": input_ids, "attention_mask": attention_mask, "offsets": offsets,
              "tokens": tokens, "context_text": self.contexts[i]}

        if self.answers is not None:
            answer_text = self.answers[i]
            start_tok_idx, end_tok_idx = get_start_end_tok_idxs(offsets, *self.start_end_idxs[i])
            res["answer_text"] = answer_text
            res["start_end_tok_idxs"] = (start_tok_idx, end_tok_idx)

        if self.text_ids is not None:
            text_id = self.text_ids[i]
            res["text_id"] = text_id

        return res

    def __len__(self): return len(self.contexts)

# Cell
class TSEDataAugmentor:
    def __init__(self, tokenizer, input_ids, attention_mask, start_position, end_position):

        self.tokenizer = tokenizer
        self.input_ids = input_ids
        self.attention_mask = attention_mask

        # initial answer start and end positions
        self.ans_start_pos, self.ans_end_pos = start_position.item(), end_position.item()

        # context token start and end excluding bos - eos tokens
        self.context_start_pos = 4
        self.context_end_pos = torch.where(attention_mask)[0][-1].item() - 1




    # left and right indexes excluding answer tokens and eos token
    @property
    def left_idxs(self): return np.arange(self.context_start_pos, self.ans_start_pos)

    @property
    def right_idxs(self): return np.arange(self.ans_end_pos+1, self.context_end_pos+1)

    @property
    def left_right_idxs(self): return np.concatenate([self.left_idxs, self.right_idxs])

    @property
    def rand_left_idx(self): return np.random.choice(self.left_idxs) if self.left_idxs.size > 0 else None

    @property
    def rand_right_idx(self): return np.random.choice(self.right_idxs) if self.right_idxs.size > 0 else None



    def right_truncate(self, right_idx):
        """
        Truncate context from random right index to beginning, answer pos doesn't change
        Note: token_type_ids NotImplemented
        """
        if not right_idx: raise Exception("Right index can't be None")

        # clone for debugging
        new_input_ids = self.input_ids.clone()
        nopad_input_ids = new_input_ids[self.attention_mask.bool()]

        # truncate from right idx to beginning - add eos_token_id to end
        truncated = torch.cat([nopad_input_ids[:right_idx+1], tensor([self.tokenizer.eos_token_id])])

        # pad new context until size are equal
        # replace original input context with new
        n_pad = len(nopad_input_ids) - len(truncated)
        new_context = F.pad(truncated, (0,n_pad), value=self.tokenizer.pad_token_id)
        new_input_ids[:self.context_end_pos+2] = new_context


        # find new attention mask, update new context end position (exclude eos token)
        # Note: context start doesn't change since we don't manipulate question
        new_attention_mask = tensor([1 if i != 1 else 0 for i in new_input_ids])
        new_context_end_pos = torch.where(new_attention_mask)[0][-1].item() - 1
        self.context_end_pos = new_context_end_pos

        # update input_ids and attention_masks
        self.input_ids = new_input_ids
        self.attention_mask = new_attention_mask

        return self.input_ids, self.attention_mask, (tensor(self.ans_start_pos), tensor(self.ans_end_pos))

    def random_right_truncate(self):
        right_idx = self.rand_right_idx
        if right_idx: self.right_truncate(right_idx)


    def left_truncate(self, left_idx):
        """
        Truncate context from random left index to end, answer pos changes too
        Note: token_type_ids NotImplemented
        """

        if not left_idx: raise Exception("Left index can't be None")

        # clone for debugging
        new_input_ids = self.input_ids.clone()

        # pad new context until size are equal
        # replace original input context with new

        n_pad = len(new_input_ids[self.context_start_pos:]) - len(new_input_ids[left_idx:])

        new_context = F.pad(new_input_ids[left_idx:], (0,n_pad), value=self.tokenizer.pad_token_id)

        new_input_ids[self.context_start_pos:] = new_context


        # find new attention mask, update new context end position (exclude eos token)
        # Note: context start doesn't change since we don't manipulate question
        new_attention_mask = tensor([1 if i != 1 else 0 for i in new_input_ids])
        new_context_end_pos = torch.where(new_attention_mask)[0][-1].item() - 1
        self.context_end_pos = new_context_end_pos

        # find new answer start and end positions
        # update new answer start and end positions
        ans_shift = left_idx - self.context_start_pos
        self.ans_start_pos, self.ans_end_pos = self.ans_start_pos-ans_shift, self.ans_end_pos-ans_shift


        # update input_ids and attention_masks
        self.input_ids = new_input_ids
        self.attention_mask = new_attention_mask

        return self.input_ids, self.attention_mask, (tensor(self.ans_start_pos), tensor(self.ans_end_pos))

    def random_left_truncate(self):
        left_idx = self.rand_left_idx
        if left_idx: self.left_truncate(left_idx)


    def replace_with_mask(self, idxs_to_mask):
        """
        Replace given input ids with tokenizer.mask_token_id
        """
        # clone for debugging
        new_input_ids = self.input_ids.clone()
        new_input_ids[idxs_to_mask] = tensor([self.tokenizer.mask_token_id]*len(idxs_to_mask))
        self.input_ids = new_input_ids


    def random_replace_with_mask(self, mask_p=0.2):
        """
        mask_p: Proportion of tokens to replace with mask token id
        """
        idxs_to_mask = np.random.choice(self.left_right_idxs, int(len(self.left_right_idxs)*mask_p))
        if idxs_to_mask.size > 0: self.replace_with_mask(idxs_to_mask)



# Cell
do_tfms = {}
do_tfms["random_left_truncate"] = {"p":.3}
do_tfms["random_right_truncate"] = {"p":.3}
do_tfms["random_replace_with_mask"] = {"p":.3, "mask_p":0.2}
do_tfms

# Cell
class TSEDataset(Dataset):
    def __init__(self, inputs, tokenizer=None, is_test=False, do_tfms:Dict=None):

        # eval
        self.inputs = inputs
#         answer_text = train_inputs[i]['answer_text']
#         context_text = train_inputs[i]['context_text']
#         offsets = train_inputs[i]['offsets']
        # augmentation
        self.is_test = is_test
        self.tokenizer = tokenizer
        self.do_tfms = do_tfms


    def __getitem__(self, i):
        'fastai requires (xb, yb) to return'

        input_ids = tensor(self.inputs[i]['input_ids'])
        attention_mask = tensor(self.inputs[i]['attention_mask'])

        if not self.is_test:
            start_position, end_position = self.inputs[i]['start_end_tok_idxs']
            start_position, end_position = tensor(start_position), tensor(end_position)

            if self.do_tfms:
                augmentor = TSEDataAugmentor(self.tokenizer, input_ids,
                                             attention_mask, start_position, end_position)

                if np.random.uniform() < self.do_tfms["random_left_truncate"]["p"]:
                    augmentor.random_left_truncate()
                if np.random.uniform() < self.do_tfms["random_right_truncate"]["p"]:
                    augmentor.random_right_truncate()
                if np.random.uniform() < self.do_tfms["random_replace_with_mask"]["p"]:
                    augmentor.random_replace_with_mask(self.do_tfms["random_replace_with_mask"]["mask_p"])

                input_ids = augmentor.input_ids
                attention_mask = augmentor.attention_mask
                start_position, end_position = tensor(augmentor.ans_start_pos), tensor(augmentor.ans_end_pos)


        xb = (input_ids, attention_mask)
        if not self.is_test: yb = (start_position, end_position)
        else: yb = (0,0)

        return xb, yb

    def __len__(self): return len(self.inputs)