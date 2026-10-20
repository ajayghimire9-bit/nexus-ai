"""Optional rank-four READOUT representation; never writes recurrent h or z.

Not enabled in the controller. Evaluating it requires a separate source fit,
fresh assessment and retention evidence; functional tests are not that evidence.
"""
import torch
from torch import nn


class HiddenResidual(nn.Module):
    def __init__(self):
        super().__init__();self.U=nn.Parameter(torch.zeros(32,4));self.V=nn.Parameter(torch.randn(4,32)*.02)

    def forward(self,h):
        if h.shape[-1]!=32:raise ValueError('hidden_width_32_required')
        return h+(h@self.V.T)@self.U.T
