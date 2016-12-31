import time

import matplotlib.pyplot as plt
import nengo
import nengo_ocl
import numpy as np

import nengo_deeplearning as nengo_dl


def cconv(dimensions, neurons_per_d, neuron_type):
    with nengo.Network(label="cconv") as net:
        net.config[nengo.Ensemble].neuron_type = neuron_type
        net.config[nengo.Ensemble].gain = nengo.dists.Choice([1])
        net.config[nengo.Ensemble].bias = nengo.dists.Choice([0])

        cconv = nengo.networks.CircularConvolution(neurons_per_d, dimensions)

        inp_a = nengo.Node([0] * dimensions)
        inp_b = nengo.Node([1] * dimensions)
        nengo.Connection(inp_a, cconv.A)
        nengo.Connection(inp_b, cconv.B)

        nengo.Probe(cconv.output)

    return net


def integrator(dimensions, neurons_per_d, neuron_type):
    with nengo.Network(label="integrator") as net:
        net.config[nengo.Ensemble].neuron_type = neuron_type
        net.config[nengo.Ensemble].gain = nengo.dists.Choice([1])
        net.config[nengo.Ensemble].bias = nengo.dists.Choice([0])

        integ = nengo.networks.Integrator(0.1, neurons_per_d * dimensions,
                                          dimensions)

        inp = nengo.Node([0] * dimensions)
        nengo.Connection(inp, integ.input)

        nengo.Probe(integ.ensemble)

    return net


def pes(dimensions, neurons_per_d, neuron_type):
    with nengo.Network(label="pes") as net:
        net.config[nengo.Ensemble].neuron_type = neuron_type
        net.config[nengo.Ensemble].gain = nengo.dists.Choice([1])
        net.config[nengo.Ensemble].bias = nengo.dists.Choice([0])

        inp = nengo.Node([1] * dimensions)
        pre = nengo.Ensemble(neurons_per_d * dimensions, dimensions)
        post = nengo.Ensemble(neurons_per_d * dimensions, dimensions)
        err = nengo.Node(size_in=dimensions)
        nengo.Connection(inp, pre)
        nengo.Connection(post, err, transform=-1)
        nengo.Connection(inp, err)

        conn = nengo.Connection(pre, post, learning_rule_type=nengo.PES())
        nengo.Connection(err, conn.learning_rule)

        nengo.Probe(post)

    return net


def compare_backends():
    # benchmarks = [pes, integrator]
    benchmarks = [cconv]
    n_range = [32]
    d_range = [64, 128, 256, 512]
    neuron_types = [nengo.RectifiedLinear]  # , nengo.LIF]
    backends = [nengo_dl, nengo, nengo_ocl]

    data = np.zeros((len(benchmarks), len(n_range), len(d_range),
                     len(neuron_types), len(backends)))

    for i, bench in enumerate(benchmarks):
        for j, neurons in enumerate(n_range):
            for k, dimensions in enumerate(d_range):
                for l, neuron_type in enumerate(neuron_types):
                    print("-" * 30)
                    print(bench, neurons, dimensions, neuron_type)

                    net = bench(dimensions, neurons, neuron_type())
                    model = nengo.builder.Model()
                    model.build(net)

                    for m, backend in enumerate(backends):
                        print(backend)
                        if backend == nengo_dl:
                            kwargs = {"max_run_steps": 5000,
                                      "device": "/cpu:0"}
                        else:
                            kwargs = {}
                        try:
                            with backend.Simulator(None, model=model,
                                                   **kwargs) as sim:
                                start = time.time()
                                sim.run(5.0)
                                data[i, j, k, l, m] = time.time() - start
                        except Exception as e:
                            print(backend, "CRASHED")
                            print(e)
                            data[i, j, k, l, m] = np.nan

    np.savez("benchmark_data.npz", data)

    # data = np.load("benchmark_data.npz")["arr_0"]

    bench_names = ["pes", "integrator", "cconv"]
    neuron_names = ["relu"]
    for i in range(len(benchmarks)):
        for j in range(len(neuron_types)):
            plt.figure()
            plt.title("%s (%s)" % (bench_names[i], neuron_names[j]))
            plt.plot(d_range, data[i, 0, :, j, 0] / data[i, 0, :, j, 1])
            plt.xlabel("dimensions")
            plt.ylabel("nengo_dl / nengo")

            plt.figure()
            plt.title("%s (%s)" % (bench_names[i], neuron_names[j]))
            plt.plot(d_range, data[i, 0, :, j, 0] / data[i, 0, :, j, 2])
            plt.xlabel("dimensions")
            plt.ylabel("nengo_dl / nengo_ocl")

            plt.figure()
            plt.title("%s (%s)" % (bench_names[i], neuron_names[j]))
            plt.plot(d_range, data[i, 0, :, j, :])
            plt.xlabel("dimensions")
            plt.ylabel("seconds")
            plt.legend(["nengo_dl", "nengo", "nengo_ocl"])

    plt.show()


def profiling():
    # note: in order for profiling to work, you have to manually add
    # ...\CUDA\v8.0\extras\CUPTI\libx64 to the path
    net = cconv(128, 32, nengo.RectifiedLinear())
    with nengo_dl.Simulator(net, tensorboard=False, max_run_steps=1, device="/cpu:0") as sim:
        sim.run_steps(1, profile=True)


if __name__ == "__main__":
    compare_backends()
    # profiling()
