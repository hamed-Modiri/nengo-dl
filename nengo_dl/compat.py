# pylint: disable=unused-import,ungrouped-imports

"""
Utilities to ease cross-compatibility between different versions of upstream
dependencies.
"""

from collections import OrderedDict
import inspect

import nengo
from nengo._vendor.scipy.sparse import linalg_interface, linalg_onenormest
from packaging import version
import tensorflow as tf
from tensorflow.python.keras import backend


# TensorFlow compatibility


class TFLogFilter:
    """
    Filter for cleaning up the TensorFlow log output.

    Parameters
    ----------
    err_on_deprecation : bool
        If True, treat deprecation log messages as errors.
    """

    def __init__(self, err_on_deprecation):
        self.err_on_deprecation = err_on_deprecation

    def filter(self, record):
        """
        Apply filter to log record.

        Parameters
        ----------
        record : `LogRecord`
            Message emitted by logger.

        Returns
        -------
        pass : bool
            If True, pass the ``record``, otherwise filter it out.

        Raises
        ------
        AttributeError
            If a deprecation message is detected and ``err_on_deprecation=True``.
        """

        # "constraint is deprecated": Keras' Layer.add_weight adds the
        # constraint argument, so this is not in our control
        if len(record.args) > 3 and record.args[3] == "constraint":
            return False

        # "tf.keras.backend.get_session is deprecated": this deprecation message
        # is raised incorrectly due to a bug, see
        # https://github.com/tensorflow/tensorflow/issues/33182
        if len(record.args) > 1 and record.args[1] == "tf.keras.backend.get_session":
            return False

        # "Output steps_run missing from loss dictionary": steps_run should
        # never have a loss defined
        if record.msg.startswith("Output steps_run missing from loss dictionary"):
            return False

        if self.err_on_deprecation and (
            "deprecation.py" in record.pathname or "deprecated" in record.msg.lower()
        ):
            msg = record.getMessage()
            raise AttributeError("Deprecation warning detected:\n%s" % msg)

        return True


tf.get_logger().addFilter(TFLogFilter(err_on_deprecation=False))

if version.parse(tf.__version__) < version.parse("2.2.0rc0"):

    def global_learning_phase():
        """Returns the global (eager) Keras learning phase."""

        return backend._GRAPH_LEARNING_PHASES.get(backend._DUMMY_EAGER_GRAPH, None)

    def tensor_ref(tensor):
        """Return (experimental) Tensor ref (can be used as dict key)."""

        return tensor.experimental_ref()


else:

    def global_learning_phase():
        """Returns the global (eager) Keras learning phase."""

        return backend._GRAPH_LEARNING_PHASES.get(backend._DUMMY_EAGER_GRAPH.key, None)

    def tensor_ref(tensor):
        """Return Tensor ref (can be used as dict key)."""

        return tensor.ref()

    if (
        version.parse("2.2.0")
        <= version.parse(tf.__version__)
        < version.parse("2.3.0rc0")
    ):
        from tensorflow.python.keras.engine import network

        # monkeypatch to fix bug in TF2.2, see
        # https://github.com/tensorflow/tensorflow/issues/37548
        old_conform = network.Network._conform_to_reference_input

        def _conform_to_reference_input(self, tensor, ref_input):
            keras_history = getattr(tensor, "_keras_history", None)

            tensor = old_conform(self, tensor, ref_input)

            if keras_history is not None:
                tensor._keras_history = keras_history

            return tensor

        network.Network._conform_to_reference_input = _conform_to_reference_input

if version.parse(tf.__version__) < version.parse("2.1.0rc0"):
    from tensorflow.python.keras.layers import (
        BatchNormalization as BatchNormalizationV1,
    )
    from tensorflow.python.keras.layers import BatchNormalizationV2
else:
    from tensorflow.python.keras.layers import (
        BatchNormalizationV1,
        BatchNormalizationV2,
    )

# Nengo compatibility

# monkeypatch fix for https://github.com/nengo/nengo/pull/1587
linalg_onenormest.aslinearoperator = linalg_interface.aslinearoperator

if version.parse(nengo.__version__) < version.parse("3.1.0.dev0"):
    PoissonSpiking = RegularSpiking = StochasticSpiking = Tanh = NoTransform = type(
        None
    )

    default_transform = 1

    def conn_has_weights(conn):
        """All connections have weights."""
        return True

    def neuron_state(neuron_op):
        """Look up keys from function signature."""
        names = list(inspect.signature(neuron_op.neurons.step_math).parameters.keys())[
            3:
        ]
        assert len(names) == len(neuron_op.states)
        return OrderedDict((n, s) for n, s in zip(names, neuron_op.states))

    def neuron_step(neuron_op, dt, J, output, state):  # pragma: no cover (runs in TF)
        """Call step_math instead of step."""
        neuron_op.neurons.step_math(dt, J, output, *state.values())


else:
    from nengo.neurons import PoissonSpiking, RegularSpiking, StochasticSpiking, Tanh
    from nengo.transforms import NoTransform

    default_transform = None

    def conn_has_weights(conn):
        """Equivalent to conn.has_weights."""
        return conn.has_weights

    def neuron_state(neuron_op):
        """Equivalent to neuron_op.state."""
        return neuron_op.state

    def neuron_step(neuron_op, dt, J, output, state):  # pragma: no cover (runs in TF)
        """Equivalent to neuron_op.step."""
        neuron_op.neurons.step(dt, J, output, **state)
