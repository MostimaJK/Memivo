"""Execution evidence is derived from running tensors or ONNX node profiles, never a preference."""
import json
from pathlib import Path
import sys


def model_tensor_device(owner):
    # Ultralytics AutoBackend may expose no parameters itself, while its
    # wrapped DetectionModel owns the actual tensors.
    model=getattr(owner,'model',None)
    for _ in range(4):
        if model is None:return None
        try:return next(model.parameters()).device
        except (AttributeError,StopIteration):model=getattr(model,'model',None)
    return None


def torch_execution(requested, device, operation):
    actual=str(device) if device is not None else 'unknown'
    if actual=='0':actual='unknown'  # an input argument is not execution evidence
    if requested=='cuda' and actual!='unknown' and not actual.startswith('cuda'):
        raise RuntimeError(f'Requested CUDA but {operation} actually executed on {actual}; refusing CPU fallback.')
    if requested=='cpu' and actual!='unknown' and actual!='cpu':
        raise RuntimeError(f'Requested CPU but {operation} actually executed on {actual}.')
    torch=sys.modules.get('torch')
    report=dict(operation=operation,requested=requested,actual=actual,
                evidence='tensor_device' if actual!='unknown' else 'unverified')
    if actual.startswith('cuda') and torch:report['gpu_name']=torch.cuda.get_device_name(device)
    return report


def torch_memory_snapshot(device):
    """Observe an already loaded torch runtime; never initialize CUDA for UI stats.

    Peak counters cover the worker lifetime, rather than resetting global state
    between operations. These numbers exclude other processes and ORT arenas.
    """
    torch = sys.modules.get('torch')
    if not torch or not str(device).startswith('cuda'):
        return {}
    try:
        functions = dict(allocated_mb='memory_allocated', reserved_mb='memory_reserved',
                         worker_peak_allocated_mb='max_memory_allocated',
                         worker_peak_reserved_mb='max_memory_reserved')
        return {key: round(getattr(torch.cuda, name)(device)/1024**2, 2)
                for key, name in functions.items() if callable(getattr(torch.cuda, name, None))}
    except (RuntimeError, ValueError):
        # Optional diagnostics cannot turn an otherwise successful task into failure.
        return {}


def onnx_profile(path):
    counts={}
    for event in json.loads(Path(path).read_text(encoding='utf-8')):
        provider=event.get('args',{}).get('provider')
        if event.get('cat')=='Node' and provider:counts[provider]=counts.get(provider,0)+1
    return counts


def face_execution(requested, profiles):
    active={stage:counts for stage,counts in profiles.items() if sum(counts.values())}
    if not active:return dict(operation='recognize',requested=requested,actual='cache',evidence='feature_cache',nodes=profiles)
    if requested=='cpu' and any(counts.get('CUDAExecutionProvider') for counts in active.values()):
        raise RuntimeError('Requested CPU but face nodes executed on CUDA.')
    if requested=='cuda' and any(not counts.get('CUDAExecutionProvider') for counts in active.values()):
        raise RuntimeError('Requested CUDA but an active face model executed only CPU nodes; refusing GPU success.')
    return dict(operation='recognize',requested=requested,actual='cuda:0' if requested=='cuda' else 'cpu',
                evidence='onnx_node_profile',nodes=profiles,
                cpu_nodes=sum(c.get('CPUExecutionProvider',0) for c in active.values()))
