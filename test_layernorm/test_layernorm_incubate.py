import numpy as np
import paddle
import unittest
from paddle.fluid.layers.utils import map_structure
import sys
sys.path.append("..")
from utils import TOLERANCE

class TestLayerNormIncubateCase1_FP32(unittest.TestCase):
    def setUp(self):
        self.init_params()
        self.init_threshold()
        self.init_np_inputs_and_dout()

    def init_params(self):
        self.np_input_dir = "./inputs_case1.npz"
        self.epsilon = 1e-05
        self.begin_norm_axis = 1
        self.dtype = "float32"
        self.save_static_res_path = "./static_develop_res_case1_fp32.npz"
        self.save_eager_res_path = "./eager_develop_res_case1_fp32.npz"
    
    def init_threshold(self):
        self.atol = TOLERANCE[self.dtype]["atol"]
        self.rtol = TOLERANCE[self.dtype]["rtol"]

    def init_np_inputs_and_dout(self):
        np_inputs_array = np.load(self.np_input_dir)
        # get np array from npz file
        self.np_x = np_inputs_array["x"]
        self.np_weight = np_inputs_array["weight"]
        self.np_bias = np_inputs_array["bias"]
        self.np_dout = np_inputs_array["dout"]
        # convert np array dtype
        if self.dtype == "float16":
            self.np_x = self.np_x.astype("float16")
            self.np_weight = self.np_weight.astype("float16")
            self.np_bias = self.np_bias.astype("float16")
            self.np_dout = self.np_dout.astype("float16")
    
    def gen_eager_inputs_and_dout(self):
        x_eager = paddle.to_tensor(
            self.np_x,
            dtype=self.dtype if self.dtype != 'bfloat16' else "float32",
            place="gpu",
        )
        x_eager.stop_gradient = False
        weight_eager = paddle.to_tensor(
            self.np_weight,
            dtype=self.dtype if self.dtype != 'bfloat16' else "float32",
            place="gpu",
        )
        weight_eager.stop_gradient = False
        bias_eager = paddle.to_tensor(
            self.np_bias,
            dtype=self.dtype if self.dtype != 'bfloat16' else "float32",
            place="gpu",
        )
        bias_eager.stop_gradient = False
        dout_eager = paddle.to_tensor(
            self.np_dout,
            dtype=self.dtype if self.dtype != 'bfloat16' else "float32",
            place="gpu",
        )
        dout_eager.stop_gradient = False
        return x_eager, weight_eager, bias_eager, dout_eager
    
    def cal_eager_res(self, x, weight, bias, dout):
        x_t = x
        weight_t = weight
        bias_t = bias
        dout_t = dout
        if self.dtype == "bfloat16":
            x_t = paddle.cast(x, dtype="uint16")
            weight_t = paddle.cast(weight, dtype="uint16")
            bias_t = paddle.cast(bias, dtype="uint16")
            dout_t = paddle.cast(dout, dtype="uint16")
        out = paddle.nn.functional.layer_norm(x_t, x_t.shape[self.begin_norm_axis:], weight_t, bias_t, self.epsilon)
        out_grads = paddle.grad([out], [x, weight, bias], grad_outputs=[dout_t])
        if self.dtype == "bfloat16":
            out = paddle.cast(out, dtype="float32")
        return out, out_grads
    
    def test_eager_accuracy(self):
        # get develop eager res
        develop_res_array = np.load(self.save_eager_res_path)
        out_eager_develop = develop_res_array["out_eager"]
        out_eager_grad_0_develop = develop_res_array["out_grads_eager_0"]
        out_eager_grad_1_develop = develop_res_array["out_grads_eager_1"]
        out_eager_grad_2_develop = develop_res_array["out_grads_eager_2"]
        out_eager_grads_develop = [out_eager_grad_0_develop, out_eager_grad_1_develop, out_eager_grad_2_develop]

        # calculate incubate eager res
        x_eager, weight_eager, bias_eager, dout_eager = self.gen_eager_inputs_and_dout()
        out_eager, out_grads_eager = self.cal_eager_res(x_eager, weight_eager, bias_eager, dout_eager)
        del x_eager
        del weight_eager 
        del bias_eager
        del dout_eager
        paddle.device.cuda.empty_cache()
        out_eager_np = out_eager.numpy()
        out_grads_eager_np = map_structure(
                                lambda x: x.numpy(),
                                out_grads_eager,
                            )
        del out_eager
        del out_grads_eager
        paddle.device.cuda.empty_cache()
        # compare incubate eager res with develop eager res
        np.testing.assert_equal(
            out_eager_np,
            out_eager_develop,
            err_msg=(
                'Incubate: compare layer_norm incubate eager forward res with develop eager forward res failed in %s dtype'
            )
            % self.dtype,
        )
        for idx in range(len(out_grads_eager_np)):
            np.testing.assert_equal(
                out_grads_eager_np[idx],
                out_eager_grads_develop[idx],
            err_msg=(
                'Incubate: compare layer_norm incubate eager grad res with develop eager grad res failed in %s dtype'
            )
                % self.dtype,
            )

    def gen_static_inputs_and_dout(self):
        x_static = paddle.static.data(
            name='x',
            shape=self.np_x.shape,
            dtype=self.dtype if self.dtype != "bfloat16" else "float32",
        )
        x_static.stop_gradient = False
        weight_static = paddle.create_parameter(
            name='weight',
            shape=self.np_weight.shape,
            dtype=self.dtype if self.dtype != "bfloat16" else "float32",
        )
        weight_static.stop_gradient = False
        bias_static = paddle.create_parameter(
            name='bias',
            shape=self.np_bias.shape,
            dtype=self.dtype if self.dtype != "bfloat16" else "float32",
        )
        bias_static.stop_gradient = False
        dout_static = paddle.static.data(
            name='dout',
            shape=self.np_dout.shape,
            dtype=self.dtype if self.dtype != "bfloat16" else "float32",
        )
        dout_static.stop_gradient = False
        return x_static, weight_static, bias_static, dout_static



    def cal_static_res(self, x, weight, bias, dout):
        x_t = x
        weight_t = weight
        bias_t = bias
        dout_t = dout
        if self.dtype == "bfloat16":
            x_t = paddle.cast(x, dtype="uint16")
            weight_t = paddle.cast(weight, dtype="uint16")
            bias_t = paddle.cast(bias, dtype="uint16")
            dout_t = paddle.cast(dout, dtype="uint16")
        out = paddle.nn.functional.layer_norm(x_t, x_t.shape[self.begin_norm_axis:], weight_t, bias_t, self.epsilon)
        out_grads = paddle.static.gradients([out], [x, weight, bias], target_gradients=[dout_t])
        
        if self.dtype == "bfloat16":
            out = paddle.cast(out, dtype="float32")
        return out, out_grads


    
    def test_static_accuracy(self):
        # get develop static res
        develop_res_array = np.load(self.save_static_res_path)
        out_static_develop = develop_res_array["out_static"]
        out_grads_static_0_develop = develop_res_array["out_grads_static_0"]
        out_grads_static_1_develop = develop_res_array["out_grads_static_1"]
        out_grads_static_2_develop = develop_res_array["out_grads_static_2"]
        out_grads_static_develop = [out_grads_static_0_develop, out_grads_static_1_develop, out_grads_static_2_develop]

        # calculate incubate static res
        with paddle.fluid.framework._dygraph_guard(None):
            mp, sp = paddle.static.Program(), paddle.static.Program()
            with paddle.static.program_guard(mp, sp):
                x_static, weight_static, bias_static, dout_static = self.gen_static_inputs_and_dout()
                (out_static, out_grads_static) = self.cal_static_res(
                    x_static,
                    weight_static,
                    bias_static,
                    dout_static,
            )
            exe = paddle.static.Executor(
                place=paddle.CUDAPlace(0)
            )
            exe.run(sp)
            out = exe.run(
                mp,
                feed={"x": self.np_x, "weight": self.np_weight, "bias": self.np_bias, "dout": self.np_dout},
                fetch_list=[out_static] + out_grads_static,
            )
            out_static, out_grads_static = out[0], out[1:]
        
        # compare incubate static res with develop static res
        np.testing.assert_equal(
            out_static,
            out_static_develop,
            err_msg=(
                'Incubate: compare layer_norm incubate static forward res with develop static forward res failed in %s dtype'
            )
            % self.dtype,
        )
        for idx in range(len(out_grads_static)):
            np.testing.assert_equal(
                out_grads_static[idx],
                out_grads_static_develop[idx],
            err_msg=(
                'Incubate: compare layer_norm incubate static grad res with develop static grad res failed in %s dtype'
            )
                % self.dtype,
            )

    def test_eager_stability(self):
        x_eager, weight_eager, bias_eager, dout_eager = self.gen_eager_inputs_and_dout()
        out_eager_baseline, out_grads_eager_baseline = self.cal_eager_res(x_eager, weight_eager, bias_eager, dout_eager)
        
        out_eager_baseline_np = out_eager_baseline.numpy()
        out_grads_eager_baseline_np = map_structure(
                                lambda x: x.numpy(),
                                out_grads_eager_baseline,
                            )
        del out_eager_baseline
        del out_grads_eager_baseline
        paddle.device.cuda.empty_cache()

        for i in range(50):
            out_eager, out_grads_eager = self.cal_eager_res(x_eager, weight_eager, bias_eager, dout_eager)
            out_eager = out_eager.numpy()
            out_grads_eager = map_structure(
                                    lambda x: x.numpy(),
                                    out_grads_eager,
                                )
            np.testing.assert_equal(
                out_eager,
                out_eager_baseline_np,
                err_msg=(
                    'Develop: paddle.nn.functional.layer_norm eager forward is unstable in %s dtype'
                )
                % self.dtype,
            )
            for idx in range(len(out_grads_eager)):
                np.testing.assert_equal(
                    out_grads_eager[idx],
                    out_grads_eager_baseline_np[idx],
                    err_msg=(
                        'Develop: paddle.nn.functional.layer_norm eager grad is unstable in %s dtype'
                    )
                    % self.dtype,
                )

    def test_static_stability(self):
        with paddle.fluid.framework._dygraph_guard(None):
            mp, sp = paddle.static.Program(), paddle.static.Program()
            with paddle.static.program_guard(mp, sp):
                x_static, weight_static, bias_static, dout_static = self.gen_static_inputs_and_dout()
                
                (out_static_pg, out_grads_static_pg) = self.cal_static_res(
                    x_static,
                    weight_static,
                    bias_static,
                    dout_static,
            )
            exe = paddle.static.Executor(
                place=paddle.CUDAPlace(0)
            )
            exe.run(sp)
            out = exe.run(
                mp,
                feed={"x": self.np_x, "weight": self.np_weight, "bias": self.np_bias, "dout": self.np_dout},
                fetch_list=[out_static_pg] + out_grads_static_pg,
            )
            out_static_baseline, out_grads_static_baseline = out[0], out[1:]
            for i in range(50):
                out = exe.run(
                    mp,
                    feed={"x": self.np_x, "weight": self.np_weight, "bias": self.np_bias, "dout": self.np_dout},
                    fetch_list=[out_static_pg] + out_grads_static_pg,
                )
                out_static, out_grads_static = out[0], out[1:]
                np.testing.assert_equal(
                    out_static,
                    out_static_baseline,
                    err_msg=(
                        'Develop: paddle.nn.functional.layer_norm static forward is unstable in %s dtype'
                    )
                    % self.dtype,
                )
                for idx in range(len(out_grads_static)):
                    np.testing.assert_equal(
                        out_grads_static[idx],
                        out_grads_static_baseline[idx],
                        err_msg=(
                            'Develop: paddle.nn.functional.layer_norm static grad is unstable in %s dtype'
                        )
                        % self.dtype,
                    )


class TestLayerNormIncubateCase1_FP16(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case1.npz"
        self.epsilon = 1e-05
        self.begin_norm_axis = 1
        self.dtype = "float16"
        self.save_static_res_path = "./static_develop_res_case1_fp16.npz"
        self.save_eager_res_path = "./eager_develop_res_case1_fp16.npz"

class TestLayerNormIncubateCase1_BFP16(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case1.npz"
        self.epsilon = 1e-05
        self.begin_norm_axis = 1
        self.dtype = "bfloat16"
        self.save_static_res_path = "./static_develop_res_case1_bf16.npz"
        self.save_eager_res_path = "./eager_develop_res_case1_bf16.npz"

class TestLayerNormIncubateCase2_FP32(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case2.npz"
        self.epsilon = 1e-05
        self.begin_norm_axis = 2
        self.dtype = "float32"
        self.save_static_res_path = "./static_develop_res_case2_fp32.npz"
        self.save_eager_res_path = "./eager_develop_res_case2_fp32.npz"

class TestLayerNormIncubateCase2_FP16(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case2.npz"
        self.epsilon = 1e-05
        self.begin_norm_axis = 2
        self.dtype = "float16"
        self.save_static_res_path = "./static_develop_res_case2_fp16.npz"
        self.save_eager_res_path = "./eager_develop_res_case2_fp16.npz"

class TestLayerNormIncubateCase2_BFP16(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case2.npz"
        self.epsilon = 1e-05
        self.begin_norm_axis = 2
        self.dtype = "bfloat16"
        self.save_static_res_path = "./static_develop_res_case2_bf16.npz"
        self.save_eager_res_path = "./eager_develop_res_case2_bf16.npz"

class TestLayerNormIncubateCase3_FP32(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case3.npz"
        self.epsilon = 1e-12
        self.begin_norm_axis = 2
        self.dtype = "float32"
        self.save_static_res_path = "./static_develop_res_case3_fp32.npz"
        self.save_eager_res_path = "./eager_develop_res_case3_fp32.npz"

class TestLayerNormIncubateCase3_FP16(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case3.npz"
        self.epsilon = 1e-12
        self.begin_norm_axis = 2
        self.dtype = "float16"
        self.save_static_res_path = "./static_develop_res_case3_fp16.npz"
        self.save_eager_res_path = "./eager_develop_res_case3_fp16.npz"

class TestLayerNormIncubateCase3_BFP16(TestLayerNormIncubateCase1_FP32):
    def init_params(self):
        self.np_input_dir = "./inputs_case3.npz"
        self.epsilon = 1e-12
        self.begin_norm_axis = 2
        self.dtype = "bfloat16"
        self.save_static_res_path = "./static_develop_res_case3_bf16.npz"
        self.save_eager_res_path = "./eager_develop_res_case3_bf16.npz"

if __name__ == '__main__':
    unittest.main()
