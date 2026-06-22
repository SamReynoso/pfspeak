import torch
from torch.nn import Module
from transformers import AlbertConfig

from pfspeak.common.dataclasses import Output
from pfspeak.tts.istftnet import Decoder
from pfspeak.tts.modules import CustomAlbert, ProsodyPredictor, TextEncoder

from pfspeak.tts.specs import ModelSpec
from typing import Tuple, Union
from torch import Tensor



class PfModel(Module):
    def __init__( self, config: ModelSpec):

        super().__init__()

        self.map_location = config.map_location
        self.weights_only = config.weights_only

        self.vocab = config.vocab
        self.bert = CustomAlbert(
                AlbertConfig(
                    vocab_size=config.n_token,
                    **config.plbert)
                )

        self.bert_encoder = torch.nn.Linear(
                self.bert.config.hidden_size,
                config.hidden_dim
                )

        self.context_length = self.bert.config.max_position_embeddings

        self.predictor = ProsodyPredictor(
                style_dim=config.style_dim,
                d_hid=config.hidden_dim,
                nlayers=config.n_layer,
                max_dur=config.max_dur,
                dropout=config.dropout
                )

        self.text_encoder = TextEncoder(
                channels=config.hidden_dim,
                kernel_size=config.text_encoder_kernel_size,
                depth=config.n_layer,
                n_symbols=config.n_token
                )

        self.decoder = Decoder(
                dim_in=config.hidden_dim,
                style_dim=config.style_dim,
                dim_out=config.n_mels,
                disable_complex=config.disable_complex,
                **config.istftnet
                )

    def load_model(self, model_path: str):

        loaded = torch.load(model_path,
                            map_location=self.map_location,
                            weights_only=self.weights_only)

        for key, state_dict in loaded.items():
            assert hasattr(self, key), key
            try:
                getattr(self, key).load_state_dict(state_dict)
            except:
                state_dict = {k[7:]: v for k, v in state_dict.items()}
                getattr(self, key).load_state_dict(state_dict, strict=False)

    @property
    def device(self):
        return self.bert.device


    @torch.no_grad()
    def forward_with_tokens(self,
                            input_ids: Tensor,
                            ref_s: Tensor,
                            speed: float = 1
                            ) -> Tuple[Tensor, Tensor]:

        input_lengths = torch.full(
            (input_ids.shape[0],), 
            input_ids.shape[-1], 
            device=input_ids.device,
            dtype=torch.long
        )

        text_mask = (
                torch.gt(
                    ( 1 + (
                        torch.arange(float(input_lengths.max()))
                        .unsqueeze(0)
                        .expand(input_lengths.shape[0], -1)
                        .type_as(input_lengths)
                        ) 
                     )
                    ,
                    input_lengths.unsqueeze(1)).to(self.device)
                )

        ref_s_tail = ref_s[:, 128:]
        ref_s_head = ref_s[:, :128]
        d = self.predictor.text_encoder(
                (
                    self.bert_encoder(
                        self.bert(
                            input_ids,
                            attention_mask=(
                                ~ text_mask
                                ).int()
                            )
                        ).transpose(-1, -2)
                    )
                ,
                ref_s_tail,
                input_lengths,
                text_mask
                ,
                )

        prediction_duration= (
                torch.round(
                    torch.sigmoid(
                        self.predictor.duration_proj(
                            # Project Long Shor Term Memory
                            self.predictor.lstm(d)[0]
                            )
                        )
                            .sum(dim=-1)
                            / speed
                    )
                .clamp(min=1)
                .long()
                .squeeze()
                )

        indices = torch.repeat_interleave(
                torch.arange(
                    input_ids.shape[1],
                    device=self.device
                    )
                ,
                prediction_duration
                )

        pred_aln_trg = torch.zeros(
                (input_ids.shape[1], indices.shape[0]
                 )
                , device=self.device
                )

        pred_aln_trg[indices, torch.arange(indices.shape[0])] = 1
        pred_aln_trg = pred_aln_trg.unsqueeze(0).to(self.device)

        F0_pred, N_pred = self.predictor.F0Ntrain(
                d.transpose(-1, -2)
                @
                pred_aln_trg
                ,
                ref_s_tail
                )

        audio = self.decoder(
                (
                    self.text_encoder(
                        input_ids,
                        input_lengths,
                        text_mask
                        )
                    @
                    pred_aln_trg
                )
                ,
                F0_pred,
                N_pred,
                ref_s_head
                ,
                ).squeeze()

        return audio, prediction_duration

    def forward(self,
                phonemes: str,
                ref_s: Tensor,
                speed: float = 1,
                return_output: bool = False
                ) -> Union[Output, Tensor]:

        input_ids = [
                self.vocab[p] 
                for p in phonemes if self.vocab.get(p) is not None
                ]

        input_ids = torch.LongTensor([[0, *input_ids, 0]]).to(self.device)
        ref_s = ref_s.to(self.device)

        assert len(input_ids) + 2 <= self.context_length, "ids > (context - 2)"
        audio, pred_dur = self.forward_with_tokens(input_ids, ref_s, speed)
        audio = audio.squeeze().cpu()

        if pred_dur is not None:
            pred_dur = pred_dur.cpu()

        if return_output:
            return Output(audio=audio, pred_dur=pred_dur)
        return audio


class KModelForONNX(torch.nn.Module):
    def __init__(self, kmodel: PfModel):
        super().__init__()
        self.kmodel = kmodel

    def forward(self,
                input_ids: torch.LongTensor,
                ref_s: torch.FloatTensor,
                speed: float = 1
                ) -> Tuple[Tensor, Tensor]:
        waveform, duration = self.kmodel.forward_with_tokens(input_ids,
                                                             ref_s, speed)
        return waveform, duration
