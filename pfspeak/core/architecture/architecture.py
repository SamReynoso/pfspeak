import torch
from torch import Tensor
from typing import Tuple
from torch.nn import Module
from .istftnet import Decoder
from transformers import AlbertConfig
from pfspeak.core.param import SpeechParams
from pfspeak.common.types import AudioPrediction
from .modules import CustomAlbert, ProsodyPredictor, TextEncoder
from pfspeak.common.exceptions import ContextLengthExceeded, UnknownPhonemeError


class KokoroArchitecture(Module):
    def __init__( self, params: SpeechParams):

        super().__init__()

        self.map_location = params.map_location
        self.weights_only = True

        self.vocab = params.vocab
        self.bert = CustomAlbert(
                AlbertConfig(
                    vocab_size=params.n_token,
                    **params.plbert)
                )

        self.bert_encoder = torch.nn.Linear(
                self.bert.config.hidden_size,
                params.hidden_dim
                )

        self.context_length = self.bert.config.max_position_embeddings

        self.predictor = ProsodyPredictor(
                style_dim=params.style_dim,
                d_hid=params.hidden_dim,
                nlayers=params.n_layer,
                max_dur=params.max_dur,
                dropout=params.dropout
                )

        self.text_encoder = TextEncoder(
                channels=params.hidden_dim,
                kernel_size=params.text_encoder_kernel_size,
                depth=params.n_layer,
                n_symbols=params.n_token
                )

        self.decoder = Decoder(
                dim_in=params.hidden_dim,
                style_dim=params.style_dim,
                dim_out=params.n_mels,
                disable_complex=params.disable_complex,
                **params.istftnet
                )

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
                ) -> AudioPrediction:

        try:

            supported = [self.vocab[p] for p in phonemes]

        except KeyError as e:
            raise UnknownPhonemeError(f"Unknown phoneme: {e.args[0]!r}") from e

        context = [0, *supported , 0]

        if len(context) > self.bert.config.max_position_embeddings:
            raise ContextLengthExceeded(
                    f"{len(context)} tokens exceeds the model limit of "
                    f"{self.bert.config.max_position_embeddings}")

        input_ids = torch.LongTensor([context]).to(self.device)

        ref_s = ref_s.to(self.device)
        audio, pred_dur = self.forward_with_tokens(input_ids, ref_s, speed)
        return audio.squeeze().cpu(), pred_dur.cpu()


class KModelForONNX(torch.nn.Module):
    def __init__(self, kmodel: KokoroArchitecture):
        super().__init__()
        self.kmodel = kmodel

    def forward(self,
                input_ids: torch.LongTensor,
                ref_s: torch.FloatTensor,
                speed: float = 1
                ) -> Tuple[Tensor, Tensor]:
        waveform, duration = self.kmodel.forward_with_tokens(
                input_ids,
                ref_s, speed
                )
        return waveform, duration
