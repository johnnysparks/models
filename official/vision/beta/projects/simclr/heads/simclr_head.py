# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Dense prediction heads."""

# Import libraries
from typing import Text, Optional

import tensorflow as tf

from official.modeling import tf_utils
from official.vision.beta.projects.simclr.modeling.layers import nn_blocks

regularizers = tf.keras.regularizers


@tf.keras.utils.register_keras_serializable(package='simclr')
class ProjectionHead(tf.keras.layers.Layer):
  def __init__(
      self,
      num_proj_layers: int = 3,
      proj_output_dim: Optional[int] = None,
      ft_proj_idx: int = 0,
      kernel_initializer: Text = 'VarianceScaling',
      kernel_regularizer: Optional[regularizers.Regularizer] = None,
      bias_regularizer: Optional[regularizers.Regularizer] = None,
      **kwargs):
    super(ProjectionHead, self).__init__(**kwargs)

    assert proj_output_dim is not None or num_proj_layers == 0
    assert ft_proj_idx <= num_proj_layers, (num_proj_layers, ft_proj_idx)

    self._proj_output_dim = proj_output_dim
    self._num_proj_layers = num_proj_layers
    self._ft_proj_idx = ft_proj_idx
    self._kernel_initializer = kernel_initializer
    self._kernel_regularizer = kernel_regularizer
    self._bias_regularizer = bias_regularizer
    self._layers = []

  def get_config(self):
    config = {
        'proj_output_dim': self._proj_output_dim,
        'num_proj_layers': self._num_proj_layers,
        'ft_proj_idx': self._ft_proj_idx,
        'kernel_initializer': self._kernel_initializer,
        'kernel_regularizer': self._kernel_regularizer,
        'bias_regularizer': self._bias_regularizer,
    }
    base_config = super(ProjectionHead, self).get_config()
    return dict(list(base_config.items()) + list(config.items()))

  def build(self, input_shape):
    if self._num_proj_layers == 0:
      pass
    else:
      intermediate_dim = int(input_shape[-1])
      for j in range(self._num_proj_layers):
        if j != self._num_proj_layers - 1:
          # for the middle layers, use bias and relu for the output.
          layer = nn_blocks.DenseBN(
              output_dim=intermediate_dim,
              use_bias=True,
              use_normalization=True,
              activation='relu',
              kernel_initializer=self._kernel_initializer,
              kernel_regularizer=self._kernel_regularizer,
              bias_regularizer=self._bias_regularizer,
              name='nl_%d' % j)
        else:
          # for the final layer, neither bias nor relu is used.
          layer = nn_blocks.DenseBN(
              output_dim=self._proj_output_dim,
              use_bias=False,
              use_normalization=True,
              activation=None,
              kernel_regularizer=self._kernel_regularizer,
              kernel_initializer=self._kernel_initializer,
              name='nl_%d' % j)
        self._layers.append(layer)
    super(ProjectionHead, self).build(input_shape)

  def call(self, inputs, training=None):
    proj_finetune_output = None
    hiddens_list = [tf.identity(inputs, 'proj_head_input')]

    if self._num_proj_layers == 0:
      proj_head_output = inputs
    else:
      for j in range(self._num_proj_layers):
        hiddens = self._layers[j](hiddens_list[-1], training)
        hiddens_list.append(hiddens)
      proj_head_output = tf.identity(hiddens_list[-1], 'proj_head_output')
      proj_finetune_output = hiddens_list[self._ft_proj_idx]

    return proj_head_output, proj_finetune_output


@tf.keras.utils.register_keras_serializable(package='simclr')
class ClassificationHead(tf.keras.layers.Layer):
  def __init__(
      self,
      num_classes: int,
      kernel_initializer: Text = 'VarianceScaling',
      kernel_regularizer: Optional[regularizers.Regularizer] = None,
      bias_regularizer: Optional[regularizers.Regularizer] = None,
      name: Text = 'head_supervised',
      **kwargs):
    super(ClassificationHead, self).__init__(name=name, **kwargs)
    self._num_classes = num_classes
    self._kernel_initializer = kernel_initializer
    self._kernel_regularizer = kernel_regularizer
    self._bias_regularizer = bias_regularizer
    self._name = name

  def get_config(self):
    config = {
        'num_classes': self._num_classes,
        'kernel_initializer': self._kernel_initializer,
        'kernel_regularizer': self._kernel_regularizer,
        'bias_regularizer': self._bias_regularizer,
    }
    base_config = super(ClassificationHead, self).get_config()
    return dict(list(base_config.items()) + list(config.items()))

  def build(self, input_shape):
    self._dense0 = nn_blocks.DenseBN(
        output_dim=self._num_classes,
        kernel_initializer=self._kernel_initializer,
        kernel_regularizer=self._kernel_regularizer,
        bias_regularizer=self._bias_regularizer,
    )
    super(ClassificationHead, self).build(input_shape)

  def call(self, inputs, training=None):
    inputs = self._dense0(inputs, training)
    inputs = tf.identity(inputs, name='logits_sup')
    return inputs