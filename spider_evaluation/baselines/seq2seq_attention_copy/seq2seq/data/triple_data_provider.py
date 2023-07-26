# Modified from parallel data provider
"""A Data Provider that reads three parallel (aligned) data files:
source, target, and schema_loc.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy as np

import tensorflow as tf
from tensorflow.contrib.slim.python.slim.data import data_provider
from tensorflow.contrib.slim.python.slim.data import parallel_reader
from seq2seq.data import split_tokens_decoder

def make_triple_data_provider(data_sources_source,
                              data_sources_target,
                              data_sources_schema,
                              reader=tf.TextLineReader,
                              num_samples=None,
                              source_delimiter=" ",
                              target_delimiter=" ",
                              **kwargs):
  """Creates a DataProvider that reads parallel text data.

  Args:
    data_sources_source: A list of data sources for the source text files.
    data_sources_target: A list of data sources for the target text files.
      Can be None for inference mode.
    data_sources_schema: A list of data sources for the schema location text files.
    num_samples: Optional, number of records in the dataset
    delimiter: Split tokens in the data on this delimiter. Defaults to space.
    kwargs: Additional arguments (shuffle, num_epochs, etc) that are passed
      to the data provider

  Returns:
    A DataProvider instance
  """
  # todo: not hard code 
  # source_delimiter="\t"
  # target_delimiter="\t"

  decoder_source = split_tokens_decoder.SplitTokensDecoder(
      tokens_feature_name="source_tokens",
      length_feature_name="source_len",
      append_token="SEQUENCE_END",
      delimiter=source_delimiter)
  print (decoder_source)
  print ("schema data source", data_sources_schema)

  dataset_source = tf.contrib.slim.dataset.Dataset(
      data_sources=data_sources_source,
      reader=reader,
      decoder=decoder_source,
      num_samples=num_samples,
      items_to_descriptions={})

  dataset_target = None
  if data_sources_target is not None:
    decoder_target = split_tokens_decoder.SplitTokensDecoder(
        tokens_feature_name="target_tokens",
        length_feature_name="target_len",
        prepend_token="SEQUENCE_START",
        append_token="SEQUENCE_END",
        delimiter=target_delimiter)

    dataset_target = tf.contrib.slim.dataset.Dataset(
        data_sources=data_sources_target,
        reader=reader,
        decoder=decoder_target,
        num_samples=num_samples,
        items_to_descriptions={})

  # decoder_schemas = split_tokens_decoder.SplitTokensDecoder(
  decoder_schemas = split_tokens_decoder.SplitMaskDecoder(
    decoder_mask_feature_name="decoder_mask",
    delimiter=" ")

  dataset_schemas = tf.contrib.slim.dataset.Dataset(
      data_sources=data_sources_schema,
      reader=reader,
      decoder=decoder_schemas,
      num_samples=num_samples,
      items_to_descriptions={})

  return TripleDataProvider(
    dataset1=dataset_source, dataset2=dataset_target,
    schemas=dataset_schemas, **kwargs)


class TripleDataProvider(data_provider.DataProvider):
  """Creates a TripleDataProvider. This data provider reads two datasets
  and their list of schemas in parallel, keep g them aligned.

  Args:
    dataset1: The first dataset. An instance of the Dataset class.
    dataset2: The second dataset. An instance of the Dataset class.
      Can be None. If None, only `dataset1` is read.
    schemas: The schema locations.
    num_readers: The number of parallel readers to use.
    shuffle: Whether to shuffle the data sources and common queue when
      reading.
    num_epochs: The number of times each data source is read. If left as None,
      the data will be cycled through indefinitely.
    common_queue_capacity: The capacity of the common queue.
    common_queue_min: The minimum number of elements in the common queue after
      a dequeue.
    seed: The seed to use if shuffling.
  """

  def __init__(self,
               dataset1,
               dataset2,
               schemas=None,
               shuffle=True,
               num_epochs=None,
               common_queue_capacity=4096,
               common_queue_min=1024,
               seed=None):

    if seed is None:
      seed = np.random.randint(10e8)

    _, data_source = parallel_reader.parallel_read(
        dataset1.data_sources,
        reader_class=dataset1.reader,
        num_epochs=num_epochs,
        num_readers=1,
        shuffle=False,
        capacity=common_queue_capacity,
        min_after_dequeue=common_queue_min,
        seed=seed)

    data_target = ""
    if dataset2 is not None:
      _, data_target = parallel_reader.parallel_read(
          dataset2.data_sources,
          reader_class=dataset2.reader,
          num_epochs=num_epochs,
          num_readers=1,
          shuffle=False,
          capacity=common_queue_capacity,
          min_after_dequeue=common_queue_min,
          seed=seed)

    data_schemas = ""
    print ("schemas.data_sources", schemas.data_sources)
    if schemas is not None:
      _, data_schemas = parallel_reader.parallel_read(
            schemas.data_sources,
            reader_class=schemas.reader,
            num_epochs=num_epochs,
            num_readers=1,
            shuffle=False,
            capacity=common_queue_capacity,
            min_after_dequeue=common_queue_min,
            seed=seed)

    # Optionally shuffle the data
    if shuffle:
      shuffle_queue = tf.RandomShuffleQueue(
          capacity=common_queue_capacity,
          min_after_dequeue=common_queue_min,
          dtypes=[tf.string, tf.string, tf.string],
          seed=seed)
      enqueue_ops = []
      enqueue_ops.append(shuffle_queue.enqueue([data_source, data_target, data_schemas]))
      tf.train.add_queue_runner(
          tf.train.QueueRunner(shuffle_queue, enqueue_ops))
      data_source, data_target, data_schemas = shuffle_queue.dequeue()

    # Decode source items
    items = dataset1.decoder.list_items()
    tensors = dataset1.decoder.decode(data_source, items)

    if dataset2 is not None:
      # Decode target items
      items2 = dataset2.decoder.list_items()
      print ("items2", items2)
      print ("data_target", data_target)
      tensors2 = dataset2.decoder.decode(data_target, items2)

      # Merge items and results
      items = items + items2
      tensors = tensors + tensors2
    if schemas is not None:
      items_schema = schemas.decoder.list_items()
      tensors_schema = schemas.decoder.decode(data_schemas, items_schema)
      print ("items_schema", items_schema)
      print ("tensor_schema", tensors_schema)
      sess = tf.Session()
      # with tf.Session() as sess:
      #   print (tf.Tensor.eval(tensors_schema[0]))
      #   print (tf.shape(tensors_schema[0]))
      items = items + items_schema
      tensors = tensors + tensors_schema

    super(TripleDataProvider, self).__init__(
        items_to_tensors=dict(zip(items, tensors)),
        num_samples=dataset1.num_samples)
