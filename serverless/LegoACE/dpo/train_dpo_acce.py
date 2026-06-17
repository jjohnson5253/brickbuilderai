import argparse
import random
import numpy as np

import torch
import torch.nn.functional as F
from torch.optim import AdamW
from transformers import AutoImageProcessor, AutoModel
from torch.utils.data import DataLoader
from dataset.dpodataset import DPODataset, collate_fn
from model.llama_image_condition import ImageConditionModel, Llama
import os
import wandb
from tqdm import tqdm
from accelerate import Accelerator

def seed_everything(seed=2003):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True

def calculate_DPO_loss(model_preferred_logprob, model_dispreferred_logprob,
                       ref_preferred_logprob, ref_dispreferred_logprob,
                       beta=0.5):

    preferred_relative_logprob = model_preferred_logprob - ref_preferred_logprob
    dispreferred_relative_logprob = model_dispreferred_logprob - ref_dispreferred_logprob

    reward_accuracies = (preferred_relative_logprob > dispreferred_relative_logprob).float().mean()
    reward_margins = (preferred_relative_logprob - dispreferred_relative_logprob).mean()

    loss = -F.logsigmoid(beta * (preferred_relative_logprob - dispreferred_relative_logprob)).mean()

    return loss, preferred_relative_logprob.mean(), dispreferred_relative_logprob.mean(), reward_accuracies, reward_margins

def get_log_prob(logits, labels, mask):
    labels = labels.long()
    log_probs = F.log_softmax(logits, dim=-1)
    token_log_probs = torch.gather(log_probs[:, :-1, :], -1, labels.unsqueeze(-1)[:, 1:, :]).squeeze(-1)
    mask = mask.float()
    response_log_probs = (token_log_probs * mask[:, :-1]).sum(dim=-1)
    response_lengths = mask.sum(dim=-1).clamp(min=1)
    return response_log_probs / response_lengths

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=2003)
    parser.add_argument("--wandb_project", type=str, default="legoace-dpo")
    parser.add_argument("--save_dir", type=str, default="output/dpo")
    parser.add_argument("--dataset_name", type=str, required=True, help="Dataset name used by the LDR tokenizer")
    parser.add_argument("--dataset_path", type=str, required=True, help="Path to DPO preference JSON file")
    parser.add_argument("--ldr_dir", type=str, required=True, help="Directory of per-sample LDR files (named '{id}-{i}.ldr')")
    parser.add_argument("--ref_image_dir", type=str, required=True, help="Directory of reference 4-view images")
    parser.add_argument("--model_path", type=str, required=True, help="Path to pretrained model checkpoint")
    parser.add_argument("--pos_range", type=int, default=1280)

    args = parser.parse_args()

    seed_everything(args.seed)

    accelerator = Accelerator()
    
    if accelerator.is_local_main_process:
        wandb.login()
        wandb.init(project=args.wandb_project, config=args)

    device = accelerator.device

    dataset = DPODataset(
        args.dataset_name,
        args.dataset_path,
        ldr_dir=args.ldr_dir,
        ref_image_dir=args.ref_image_dir,
        pos_range=args.pos_range,
    )
    model_path = args.model_path
    config = Llama(
        vocab_size=dataset.get_vocab_size(),
        max_position_embeddings=5400,
        attn_implementation="flash_attention_2",
        torch_dtype=torch.bfloat16,
        eos_token_id=dataset.get_vocab_size() - 1,
    )

    load_model = ImageConditionModel.from_pretrained(model_path)
    model = ImageConditionModel(config)
    ref_model =  ImageConditionModel(config)      
    model.load_state_dict(load_model.state_dict())
    ref_model.load_state_dict(load_model.state_dict())
    del load_model

    ref_model.requires_grad_(False)

    optimizer = AdamW(model.parameters(), lr=args.lr)

    train_dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)

    # Prepare models and dataloader for distributed training
    model, ref_model, optimizer, train_dataloader = accelerator.prepare(
        model, ref_model, optimizer, train_dataloader
    )
    
    model.train()
    ref_model.eval()
    
    dino_processor = AutoImageProcessor.from_pretrained('facebook/dinov2-base', use_fast=False)
    dino_model = AutoModel.from_pretrained('facebook/dinov2-base')
    dino_model, dino_processor = accelerator.prepare(dino_model, dino_processor)

    for epoch in range(args.epochs):
        for batch in tqdm(train_dataloader, disable=not accelerator.is_local_main_process):
            optimizer.zero_grad()

            images = [item for sublist in batch['images'] for item in sublist]
            input_dino = dino_processor(images, return_tensors="pt")
            with torch.no_grad():
                condition_embeds = dino_model(**input_dino)['last_hidden_state']
                condition_embeds = condition_embeds.reshape(condition_embeds.shape[0] // 4, condition_embeds.shape[1] * 4, -1)          

            model_preferred_logits = model(input_ids=batch['chosens'], 
                                           condition_embeds=condition_embeds,
                                           attention_mask=batch['chosens_mask']).logits
            
            model_preferred_logprob = get_log_prob(
                model_preferred_logits,
                batch['chosens'],
                batch['chosens_mask']
            )

            model_dispreferred_logits = model(input_ids=batch['rejects'], 
                                           condition_embeds=condition_embeds,
                                           attention_mask=batch['rejects_mask']).logits
            
            model_dispreferred_logprob = get_log_prob(
                model_dispreferred_logits,
                batch['rejects'],
                batch['rejects_mask']
            )

            with torch.no_grad():
                ref_preferred_logits = ref_model(input_ids=batch['chosens'], 
                                           condition_embeds=condition_embeds,
                                           attention_mask=batch['chosens_mask']).logits
                
                ref_preferred_logprob = get_log_prob(
                    ref_preferred_logits,
                    batch['chosens'],
                    batch['chosens_mask']
                )

                ref_dispreferred_logits = ref_model(input_ids=batch['rejects'], 
                                           condition_embeds=condition_embeds,
                                           attention_mask=batch['rejects_mask']).logits
                
                ref_dispreferred_logprob = get_log_prob(
                    ref_dispreferred_logits,
                    batch['rejects'],
                    batch['rejects_mask']
                )

            loss, preferred_relative_logprob, dispreferred_relative_logprob, reward_accuracies, reward_margins = calculate_DPO_loss(
                model_preferred_logprob,
                model_dispreferred_logprob,
                ref_preferred_logprob,
                ref_dispreferred_logprob,
                beta=args.beta
            )

            accelerator.backward(loss)
            optimizer.step()

            if accelerator.is_local_main_process:
                wandb.log({
                    'loss': loss.item(),
                    'preferred_relative_logprob': preferred_relative_logprob.item(),
                    'dispreferred_relative_logprob': dispreferred_relative_logprob.item(),
                    'reward_accuracy': reward_accuracies.item(),
                    'reward_margin': reward_margins.item()
                })
        accelerator.wait_for_everyone()
        if (epoch+1) % 1 == 0 and accelerator.is_local_main_process:
            unwrapped_model = accelerator.unwrap_model(model)
            unwrapped_model.save_pretrained(os.path.join(args.save_dir, f"epoch-{epoch+1}"))

    accelerator.end_training()

if __name__ == "__main__":
    main()




