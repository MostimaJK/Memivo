"""Validate ONNX execution, including actual CUDA node placement."""
import json
from pathlib import Path
import tempfile


def verify_face_runtime(profile):
    from insightface.model_zoo import get_model  # noqa: F401
    from insightface.utils import face_align  # noqa: F401
    verify_onnx_execution(profile)


def verify_onnx_execution(profile):
    import numpy as np
    import onnx
    import onnxruntime as ort

    gpu = profile == 'cu128'
    if gpu:
        ort.preload_dlls(directory='')
    provider = 'CUDAExecutionProvider' if gpu else 'CPUExecutionProvider'
    if provider not in ort.get_available_providers():
        raise RuntimeError(f'{provider} unavailable; check the engine installation and NVIDIA driver.')
    helper = onnx.helper
    graph = helper.make_graph([
        helper.make_node('Conv', ['x', 'w'], ['y'], name='memivo_conv', kernel_shape=[3, 3])
    ], 'memivo_device_check',
        [helper.make_tensor_value_info('x', onnx.TensorProto.FLOAT, [1, 1, 5, 5])],
        [helper.make_tensor_value_info('y', onnx.TensorProto.FLOAT, [1, 1, 3, 3])],
        [onnx.numpy_helper.from_array(np.ones((1, 1, 3, 3), dtype=np.float32), name='w')])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    model.ir_version = 8
    with tempfile.TemporaryDirectory(prefix='memivo-onnx-check-') as folder:
        options = ort.SessionOptions()
        options.enable_profiling = True
        options.profile_file_prefix = str(Path(folder) / 'device')
        if gpu:
            options.add_session_config_entry('session.disable_cpu_ep_fallback', '1')
        session = ort.InferenceSession(model.SerializeToString(), sess_options=options, providers=[provider])
        session.disable_fallback()
        output = session.run(None, {'x': np.ones((1, 1, 5, 5), dtype=np.float32)})[0]
        np.testing.assert_allclose(output, np.full((1, 1, 3, 3), 9, dtype=np.float32))
        events = json.loads(Path(session.end_profiling()).read_text(encoding='utf-8'))
        nodes = [e.get('args', {}) for e in events if e.get('cat') == 'Node']
        if not any(n.get('op_name') == 'Conv' and n.get('provider') == provider for n in nodes):
            raise RuntimeError(f'Convolution did not execute on {provider}; refusing to report success.')
        del session
    print(json.dumps(dict(onnxruntime=ort.__version__, provider=provider, convolution='passed')))
