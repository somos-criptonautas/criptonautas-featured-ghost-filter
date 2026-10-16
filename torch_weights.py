"""Read a PyTorch state_dict (.pth zip) into numpy arrays without installing torch."""
import pickle
import zipfile

import numpy as np

_STORAGE_DTYPES = {"FloatStorage": np.float32, "HalfStorage": np.float16, "LongStorage": np.int64}


class _StateDict(dict):
    """dict that accepts the _metadata attribute torch sets on its OrderedDict."""


def load_state_dict(path):
    archive = zipfile.ZipFile(path)
    root = archive.namelist()[0].split("/")[0]

    class SafeUnpickler(pickle.Unpickler):
        # only the few names a state_dict needs; anything else could run code
        def find_class(self, module, name):
            if module == "torch._utils" and name == "_rebuild_tensor_v2":
                return _rebuild_tensor
            if module == "collections" and name == "OrderedDict":
                return _StateDict
            if module == "torch" and name in _STORAGE_DTYPES:
                return name
            raise pickle.UnpicklingError(f"refusing to load {module}.{name}")

        def persistent_load(self, pid):
            _, storage_type, key, _location, _size = pid
            raw = archive.read(f"{root}/data/{key}")
            return np.frombuffer(raw, dtype=_STORAGE_DTYPES[storage_type])

    return SafeUnpickler(archive.open(f"{root}/data.pkl")).load()


def _rebuild_tensor(storage, offset, size, stride, *_):
    return np.lib.stride_tricks.as_strided(
        storage[offset:], shape=size, strides=[s * storage.itemsize for s in stride]).copy()
