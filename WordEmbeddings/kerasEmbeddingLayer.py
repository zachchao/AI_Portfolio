import tensorflow as tf
from tensorflow import keras

import numpy as np
import matplotlib.pyplot as plt


imdb = keras.datasets.imdb
(train_data, train_labels), (test_data, test_labels) = imdb.load_data(num_words=10000)

# A dictionary mapping words to an integer index
word_index = imdb.get_word_index()

# The first indices are reserved
word_index = {k:(v+3) for k,v in word_index.items()} 
word_index["<PAD>"] = 0
word_index["<START>"] = 1
word_index["<UNK>"] = 2  # unknown
word_index["<UNUSED>"] = 3

train_data = keras.preprocessing.sequence.pad_sequences(train_data,
	value=word_index["<PAD>"],
	padding='post',
	maxlen=256)

test_data = keras.preprocessing.sequence.pad_sequences(test_data,
	value=word_index["<PAD>"],
	padding='post',
	maxlen=256)

# input shape is the vocabulary count used for the movie reviews (10,000 words)
vocab_size = 10000

model = keras.Sequential()
model.add(keras.layers.Embedding(vocab_size, 16))

model.summary()

model.compile(optimizer=tf.train.AdamOptimizer(),
	loss='binary_crossentropy',
	metrics=['accuracy'])

x_val = train_data[:10000]
partial_x_train = train_data[10000:]

y_val = train_labels[:10000]
partial_y_train = train_labels[10000:]

history = model.fit(partial_x_train,
	partial_y_train,
	epochs=40,
	batch_size=512,
	validation_data=(x_val, y_val),
	verbose=1)

results = model.evaluate(test_data, test_labels)

history_dict = history.history
history_dict.keys()

acc = history.history['acc']
val_acc = history.history['val_acc']
loss = history.history['loss']
val_loss = history.history['val_loss']

epochs = range(1, len(acc) + 1)

print(model.predict(train_data[4]))