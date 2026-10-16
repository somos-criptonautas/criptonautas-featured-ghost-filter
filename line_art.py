"""Ink lines with Informative Drawings (MIT license), no PyTorch: .pth weights -> ONNX graph -> OpenCV DNN.
Architecture follows controlnet_aux/lineart: Generator(3, 1, n_residual_blocks=3)."""
import numpy as np


def build_onnx_model(pth_path):
    """Build the ONNX graph from the .pth weights. Only needed at image build time."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    from torch_weights import load_state_dict

    weights = load_state_dict(pth_path)
    nodes, initializers = [], []
    counter = [0]

    def unique(prefix):
        counter[0] += 1
        return f"{prefix}{counter[0]}"

    def const(array):
        key = unique("c")
        initializers.append(numpy_helper.from_array(np.asarray(array), key))
        return key

    def op(op_type, inputs, **attrs):
        output = unique(op_type)
        nodes.append(helper.make_node(op_type, inputs, [output], **attrs))
        return output

    def reflect_pad(x, p):
        return op("Pad", [x, const(np.array([0, 0, p, p, 0, 0, p, p], np.int64))], mode="reflect")

    def conv(x, key, **attrs):
        return op("Conv", [x, const(weights[key + ".weight"]), const(weights[key + ".bias"])], **attrs)

    def instance_norm(x, channels):
        scale, bias = const(np.ones(channels, np.float32)), const(np.zeros(channels, np.float32))
        return op("InstanceNormalization", [x, scale, bias], epsilon=1e-5)

    def relu(x):
        return op("Relu", [x])

    x = relu(instance_norm(conv(reflect_pad("input", 3), "model0.1"), 64))
    x = relu(instance_norm(conv(x, "model1.0", strides=[2, 2], pads=[1, 1, 1, 1]), 128))
    x = relu(instance_norm(conv(x, "model1.3", strides=[2, 2], pads=[1, 1, 1, 1]), 256))
    for i in range(3):
        block = f"model2.{i}.conv_block"
        y = relu(instance_norm(conv(reflect_pad(x, 1), block + ".1"), 256))
        y = instance_norm(conv(reflect_pad(y, 1), block + ".5"), 256)
        x = op("Add", [x, y])
    for key, channels in (("model3.0", 128), ("model3.3", 64)):
        upsampled = op("ConvTranspose", [x, const(weights[key + ".weight"]), const(weights[key + ".bias"])],
                       strides=[2, 2], pads=[1, 1, 1, 1], output_padding=[1, 1])
        x = relu(instance_norm(upsampled, channels))
    op("Sigmoid", [conv(reflect_pad(x, 3), "model4.1")])
    nodes[-1].output[0] = "output"

    graph = helper.make_graph(
        nodes, "informative_drawings",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, None, None])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 1, None, None])],
        initializers)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
    onnx.checker.check_model(model)
    return model


def line_map(net, rgb):
    """rgb: uint8 HxWx3, sides multiple of 8. Returns float HxW in 0..1 where ~0 is a stroke."""
    x = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
    net.setInput(x)
    out = net.forward()[0, 0]
    assert out.shape == rgb.shape[:2] and 0.0 <= out.min() and out.max() <= 1.0
    return out
