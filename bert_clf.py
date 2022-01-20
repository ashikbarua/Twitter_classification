# -*- coding: utf-8 -*-
"""Bert_CLF.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1jYZ7XFQYjPTvwcs5eGUwGRxeg6gE88Qt
"""

!pip install pytorch-pretrained-bert pytorch-nlp

import pandas as pd 
import numpy as np 
import torch.nn as nn
from pytorch_pretrained_bert import BertTokenizer, BertModel
import torch
from torchnlp.datasets import imdb_dataset
from keras.preprocessing.sequence import pad_sequences
from sklearn.metrics import classification_report

# from google.colab import files
# uploaded = files.upload()

# from google.colab import files
# uploaded = files.upload()

'''Loading annotated dataset'''
data_antd = pd.read_csv("data/covid_related_tf_only.csv", encoding = "ISO-8859-1" ,index_col=False)
data_antd['covid_related'] = data_antd['covid_related'].astype(int)

'''Loading OSOME dataset'''
data_osome_full = pd.read_csv("data/2020-02_tweets.csv")
data_osome = data_osome_full[['tweet']]
data_osome['covid_related'] = [False]*len(data_osome)
data_osome.value_counts(data_osome['covid_related'])
data_osome['covid_related'] = data_osome['covid_related'].astype(int)

'''Splitting annotated dataset by covid_related true/false'''
data_antd_true = data_antd[data_antd['covid_related'] == 1] 
data_antd_false = data_antd[data_antd['covid_related'] == 0]

print(pd.value_counts(data_antd_true['covid_related']))
print(pd.value_counts(data_antd_false['covid_related']))


l_true = len(data_antd_true)
l_false = len(data_antd_false)
l_osome = len(data_osome)

# Annotated set and OSOME set are joined
# df_train has 50% true tweets and 50% false tweets
df_train = data_antd_true[:l_true//2].append(data_antd_false[:l_false//2]).append(data_osome[:(l_true-l_false)//2])
df_train = df_train.sample(frac=1, random_state= 24).reset_index(drop=True)
print('Train dataset value count\n{}\n'.format(pd.value_counts(df_train['covid_related'])))

df_test = data_antd_true[l_true//2:].append(data_antd_false[l_false//2:])
df_test = df_test.sample(frac=1, random_state= 24).reset_index(drop=True)
print('Test dataset value count\n{}\n'.format(pd.value_counts(df_test['covid_related'])))

train_data = []
for i in range(len(df_train)):
  row = df_train.iloc[i]
  train_data.append({'tweet':row['tweet'], 'covid_related':row['covid_related']})

test_data = []
for i in range(len(df_test)):
  row = df_test.iloc[i]
  test_data.append({'tweet':row['tweet'], 'covid_related':row['covid_related']})

train_texts, train_labels = list(zip(*map(lambda d: (d['tweet'], d['covid_related']), train_data)))
test_texts, test_labels = list(zip(*map(lambda d: (d['tweet'], d['covid_related']), test_data)))

# Bert Classifier
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased', do_lower_case=True)
train_tokens = list(map(lambda t: ['[CLS]'] + tokenizer.tokenize(t)[:511], train_texts))
test_tokens = list(map(lambda t: ['[CLS]'] + tokenizer.tokenize(t)[:511], test_texts))

train_tokens_ids = list(map(tokenizer.convert_tokens_to_ids, train_tokens))
test_tokens_ids = list(map(tokenizer.convert_tokens_to_ids, test_tokens))

train_tokens_ids = pad_sequences(train_tokens_ids, maxlen=128, truncating="post", padding="post", dtype="int")
test_tokens_ids = pad_sequences(test_tokens_ids, maxlen=128, truncating="post", padding="post", dtype="int")

train_y = np.array(train_labels) == 1
test_y = np.array(test_labels) == 1

class BertBinaryClassifier(nn.Module):
    def __init__(self, dropout=0.1):
        super(BertBinaryClassifier, self).__init__()
        self.bert = BertModel.from_pretrained('bert-base-uncased')
        self.dropout = nn.Dropout(dropout)
        self.linear = nn.Linear(768, 1)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, tokens, masks=None):
        _, pooled_output = self.bert(tokens, attention_mask=masks, output_all_encoded_layers=False)
        dropout_output = self.dropout(pooled_output)
        linear_output = self.linear(dropout_output)
        proba = self.sigmoid(linear_output)
        return proba

train_masks = [[float(i > 0) for i in ii] for ii in train_tokens_ids]
test_masks = [[float(i > 0) for i in ii] for ii in test_tokens_ids]
train_masks_tensor = torch.tensor(train_masks)
test_masks_tensor = torch.tensor(test_masks)

train_tokens_tensor = torch.tensor(train_tokens_ids)
train_y_tensor = torch.tensor(train_y.reshape(-1, 1)).float()
test_tokens_tensor = torch.tensor(test_tokens_ids)
test_y_tensor = torch.tensor(test_y.reshape(-1, 1)).float()

BATCH_SIZE = 1
EPOCHS = 1

train_dataset =  torch.utils.data.TensorDataset(train_tokens_tensor, train_masks_tensor, train_y_tensor)
train_sampler =  torch.utils.data.RandomSampler(train_dataset)
train_dataloader =  torch.utils.data.DataLoader(train_dataset, sampler=train_sampler, batch_size=BATCH_SIZE)

test_dataset =  torch.utils.data.TensorDataset(test_tokens_tensor, test_masks_tensor, test_y_tensor)
test_sampler =  torch.utils.data.SequentialSampler(test_dataset)
test_dataloader =  torch.utils.data.DataLoader(test_dataset, sampler=test_sampler, batch_size=BATCH_SIZE)

# Initializing bert clf and starting to train the model
bert_clf = BertBinaryClassifier()
optimizer = torch.optim.Adam(bert_clf.parameters(), lr=3e-6)
for epoch_num in range(EPOCHS):
    bert_clf.train()
    train_loss = 0
    for step_num, batch_data in enumerate(train_dataloader):
        token_ids, masks, labels = tuple(t for t in batch_data)
        probas = bert_clf(token_ids, masks)
        loss_func = nn.BCELoss()
        batch_loss = loss_func(probas, labels)
        train_loss += batch_loss.item()
        bert_clf.zero_grad()
        batch_loss.backward()
        optimizer.step()
        print('Epoch: ', epoch_num + 1)
        print("\r" + "{0}/{1} loss: {2} ".format(step_num, len(train_data) / BATCH_SIZE, train_loss / (step_num + 1)))

# Evaluation
bert_clf.eval()
bert_predicted = []
all_logits = []
with torch.no_grad():
    for step_num, batch_data in enumerate(test_dataloader):
      
        token_ids, masks, labels = tuple(t for t in batch_data)
        logits = bert_clf(token_ids, masks)
        loss_func = nn.BCELoss()
        loss = loss_func(logits, labels)
        numpy_logits = logits.cpu().detach().numpy()

        bert_predicted += list(numpy_logits[:, 0] > 0.5)
        all_logits += list(numpy_logits[:, 0])
        
print(classification_report(test_y, bert_predicted))

print('Training using the OSOME set', file=open("output.txt", "a"))
print(classification_report(test_y, bert_predicted), file=open("output.txt", "a"))

