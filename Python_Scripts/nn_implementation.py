#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script for testing neural net for the ML-based multiscale modelling data. 
"""
import pandas as pd
import numpy as np
import numpy.matlib
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from Utilities import D_creator
from Utilities import msa_outer_loop
from sklearn.metrics import mean_squared_error
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import SGD
from tensorflow.keras.wrappers.scikit_learn import KerasRegressor # needed for peforming CV and parameter searches
from sklearn.preprocessing import StandardScaler


#%% Import and process data
base_data = pd.read_csv('../Data/diffusionData.csv')
data_obj = D_creator(base_data, 2, 3, 1E6)
data_set = data_obj.data_set
data_set['target'] = data_set['p_m']
target = data_set['target']
data_set = data_set.drop(['dp^(n)', 'dp^(n-1)', 'p_m'], axis = 1)
times = np.unique(data_set['time']); N = len(times)  
p_i = np.unique(data_set['p_i']); K = len(p_i)
p_i_train = p_i[np.arange(0,len(p_i))%3 != 1]; K_train = len(p_i_train)
p_i_test = p_i[np.arange(0,len(p_i))%3 == 1]; K_test = len(p_i_test)
X_train = pd.DataFrame(columns = list(data_set.columns))
X_test = pd.DataFrame(columns = list(data_set.columns))

for p in p_i_train:
   X_train = X_train.append(data_set.loc[np.round(data_set['p_i'], 7) 
                                           == np.round(p, 7)], ignore_index = False)
y_train = target.loc[X_train.index]
for p in p_i_test:
   X_test = X_test.append(data_set.loc[np.round(data_set['p_i'], 7) 
                                           == np.round(p, 7)], ignore_index = False)
y_test = target.loc[X_test.index]


#%% Setup neural network model
# seeding for the stochastic learning process
from numpy.random import seed 
seed(17) 
import tensorflow as tf
tf.random.set_seed(17)

# define model
def build_nn_model():
    # create model
    model = Sequential()
    model.add(Dense(12, input_dim = 6, activation='elu', kernel_initializer = 'glorot_uniform'))
    model.add(Dense(1, activation='linear'))
    # compile model
    opt = SGD(lr = 0.01, momentum = 0.9, nesterov=True)
    model.compile(loss='mean_squared_error', optimizer=opt)
    return model

nn_model = KerasRegressor(build_fn = build_nn_model, batch_size = 128, epochs = 500)


#%% Train, test in single-step ahead mode
X_tr = X_train.drop(['p_i', 'time', 'dt^(n+1)', 'target'], axis = 1)
X_tr = X_tr.reindex(['p_f^(n-2)', 'p^(n-2)', 'p_f^(n-1)', 'p^(n-1)', 'p_f^(n)', 'p^(n)'], axis=1)
X_te = X_test.drop(['p_i', 'time', 'dt^(n+1)', 'target'], axis = 1)
X_te = X_te.reindex(['p_f^(n-2)', 'p^(n-2)', 'p_f^(n-1)', 'p^(n-1)', 'p_f^(n)', 'p^(n)'], axis=1)

# scalers
sc_x = StandardScaler()
X_tr_scaled = sc_x.fit_transform(X_tr)
X_te_scaled = sc_x.transform(X_te)
sc_y = StandardScaler()
y_tr_scaled = sc_y.fit_transform(y_train.to_numpy().reshape((-1,1)))
y_te_scaled = sc_y.transform(y_test.to_numpy().reshape((-1,1)))
scaler = {'sc_x':sc_x, 'sc_y':sc_y}

# fit and predict
nn_model.fit(X_tr_scaled, y_tr_scaled)
#nn_model.model.save('../Data/nn_model.h5')
p_nn_tr = sc_y.inverse_transform(nn_model.predict(X_tr_scaled))
RMSE_nn_tr = np.sqrt(mean_squared_error(y_train, p_nn_tr))
p_nn_te = sc_y.inverse_transform(nn_model.predict(X_te_scaled))
RMSE_nn_te = np.sqrt(mean_squared_error(y_test, p_nn_te))
print(f'Train neurel net SSA RMSE: {RMSE_nn_tr}, Test neurel net RMSE: {RMSE_nn_te}')


#%% Test multi-step ahead mode
init_test_inputs = X_te[['p_f^(n-2)', 'p^(n-2)', 'p_f^(n-1)', 'p^(n-1)', 'p_f^(n)', 'p^(n)']].to_numpy()
init_test_inputs = init_test_inputs[0::N]
p_nn_msa = msa_outer_loop(nn_model, init_test_inputs, 0.1, N, scaler = scaler)
RMSE_nn_msa = np.sqrt(mean_squared_error(y_test, p_nn_msa))
print(f'neurel net MSA RMSE: {RMSE_nn_msa}')


#%% Visualise results
blue = (0.1294, 0.4000, 0.6745)
red = (0.6980, 0.0941, 0.1686)

# training: one-step ahead
fig, ax = plt.subplots(figsize=(12, 7))
#ax.set_title('Training: SSA', fontsize=14)
start = 0; stop = N
for i in range(K_train):
    ax.semilogx(times, X_train['target'].iloc[start:stop], color = 'k', 
                alpha = 0.5, linewidth = 1)
    start += N; stop += N
train_targets =  mlines.Line2D([], [], color='k', alpha = 0.5, linewidth = 1, 
                            label='Target')
start = 0; stop = N
for i in range(K_train):
    ax.semilogx(times, p_nn_tr[start:stop], color = blue, alpha = 0.7, linewidth = 1, 
               linestyle = '--')
    start += N; stop += N
prediction =  mlines.Line2D([], [], color = blue, alpha = 0.7, linewidth = 1, 
                            linestyle = '--', label='Prediction')
ax.set_xlim([min(times), 100])
ax.set_xlabel('Time (s)', fontsize = 12)
ax.set_ylim([1.5E4, 1E6])
ax.set_ylabel('Pressure (Pa)', fontsize = 12)
ax.tick_params(labelsize=14)
ax.legend(handles=[train_targets, prediction], fontsize = 8, loc = 'lower right')
# =============================================================================
# ax.axis('off')
# fig.tight_layout(pad=0)
# ax.figure.set_size_inches(5.5/2.54, 5.5/2.54)
# plt.savefig('train_pr.png', dpi = 600)
# =============================================================================


# testing: multi-step ahead
fig, ax = plt.subplots(figsize=(12, 7))
#ax.set_title('Testing: MSA', fontsize=14)
start = 0; stop = N
for i in range(K_test):
    ax.semilogx(times, X_test['target'].iloc[start:stop], color = 'k', 
                alpha = 0.5, linewidth = 1)
    start += N; stop += N
test_targets =  mlines.Line2D([], [], color='k', alpha = 0.5, linewidth = 1, 
                             label='Target')
start = 0; stop = N
for i in range(K_test):
    ax.semilogx(times, p_nn_msa[start:stop], color = red, linewidth = 1, 
                linestyle = '--', alpha = 0.7)
    start += N; stop += N
prediction =  mlines.Line2D([], [], color = red, alpha = 0.7, linewidth = 1, 
                            linestyle = '--', label='Prediction')
ax.set_xlim([min(times), 100])
ax.set_xlabel('Time (s)', fontsize = 12)
ax.set_ylim([1.5E4, 1E6])
ax.set_ylabel('Pressure (Pa)', fontsize = 12)
ax.tick_params(labelsize=14)
ax.legend(handles=[test_targets, prediction], fontsize = 8, loc = 'lower right')
# =============================================================================
# ax.axis('off')
# fig.tight_layout(pad=0)
# ax.figure.set_size_inches(5.5/2.54, 5.5/2.54)
# plt.savefig('test_pr.png', dpi = 600)
# =============================================================================

