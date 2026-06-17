import torch
from transformers.generation.logits_process import LogitsProcessor


class DynamicRangeMaskingProcessor(LogitsProcessor):
    """Logits processor that restricts the model to brick-format-valid tokens.

    Tokens in LegoACE come in groups of five: ``(x, y, z, rotation_id, brick_type_id)``.
    This processor masks any token that falls outside the valid range for the current
    step, ensuring the model always emits a syntactically well-formed sequence.

    Token layout (low -> high vocab id):
      * 0 ..................................... BOS
      * 1 .. pos_range ........................ position values
      * pos_range+1 .. pos_range+num_rot ...... rotation ids
      * pos_range+num_rot+1 .. +num_dat ....... brick type ids
      * (last id) ............................. EOS
    """

    def __init__(self, pos_range, num_rot, num_dat, mask_value=-float("inf")):
        super().__init__()
        self.pos_range = pos_range
        self.num_rot = num_rot
        self.num_dat = num_dat
        self.mask_value = mask_value

    def get_valid_range(self, cur_len):
        if cur_len % 5 in (0, 1, 2):
            return 1, self.pos_range
        if cur_len % 5 == 3:
            return self.pos_range + 1, self.pos_range + self.num_rot
        return self.pos_range + self.num_rot + 1, self.pos_range + self.num_rot + self.num_dat

    def __call__(self, input_ids, next_token_logits):
        batch_size = next_token_logits.shape[0]
        cur_len = input_ids.shape[1] - 1
        start_token_id, end_token_id = self.get_valid_range(cur_len)

        assert start_token_id < end_token_id, f"Invalid range: {start_token_id} - {end_token_id}"
        assert end_token_id < next_token_logits.shape[-1], (
            f"End token id {end_token_id} exceeds vocab size {next_token_logits.shape[-1]}"
        )

        unwanted_mask = torch.ones(next_token_logits.shape[1], dtype=torch.bool, device=next_token_logits.device)
        unwanted_mask[start_token_id : end_token_id + 1] = False
        unwanted_mask[0] = False
        if cur_len % 5 == 0:
            # also allow EOS at the start of a new brick group
            unwanted_mask[-1] = False

        unwanted_mask = unwanted_mask.unsqueeze(0).expand(batch_size, -1)
        return next_token_logits.masked_fill(unwanted_mask, self.mask_value)
