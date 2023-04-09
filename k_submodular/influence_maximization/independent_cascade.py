"""
Implement independent cascade model
"""
#!/usr/bin/env python
#    Copyright (C) 2004-2010 by
#    Hung-Hsuan Chen <hhchen@psu.edu>
#    All rights reserved.
#    BSD license.
#    NetworkX:http://networkx.lanl.gov/.
__author__ = """Hung-Hsuan Chen (hhchen@psu.edu)"""

import copy
import networkx as nx
import random

__all__ = ['independent_cascade']

import numpy as np


def independent_cascade(G, seeds, steps=0, weighted_graph=True, copy_graph=False):
  """Return the active nodes of each diffusion step by the independent cascade
  model

  Parameters
  -----------
  G : graph
    A NetworkX graph
  seeds : list of nodes
    The seed nodes for diffusion
  steps: integer
    The number of steps to diffuse.  If steps <= 0, the diffusion runs until
    no more nodes can be activated.  If steps > 0, the diffusion runs for at
    most "steps" rounds

  Returns
  -------
  layer_i_nodes : list of list of activated nodes
    layer_i_nodes[0]: the seeds
    layer_i_nodes[k]: the nodes activated at the kth diffusion step

  Notes
  -----
  When node v in G becomes active, it has a *single* chance of activating
  each currently inactive neighbor w with probability p_{vw}

  Examples
  --------
  >>> DG = nx.DiGraph()
  >>> DG.add_edges_from([(1,2), (1,3), (1,5), (2,1), (3,2), (4,2), (4,3), \
  >>>   (4,6), (5,3), (5,4), (5,6), (6,4), (6,5)], act_prob=0.2)
  >>> layers = networkx_addon.information_propagation.independent_cascade(DG, [6])

  References
  ----------
  [1] David Kempe, Jon Kleinberg, and Eva Tardos.
      Influential nodes in a diffusion model for social networks.
      In Automata, Languages and Programming, 2005.
  """
  if type(G) == nx.MultiGraph or type(G) == nx.MultiDiGraph:
      raise Exception( \
          "independent_cascade() is not defined for graphs with multiedges.")

  # make sure the seeds are in the graph
  for s in seeds:
    if s not in G.nodes():
      raise Exception("seed", s, "is not in graph")

  # change to directed graph
  if copy_graph:
    if not G.is_directed():
      DG = G.to_directed()
    else:
      DG = copy.deepcopy(G)
  else:
    DG = G

  # init activation probabilities
  if not weighted_graph:
    for e in DG.edges():
      if 'act_prob' not in DG[e[0]][e[1]]:
        DG[e[0]][e[1]]['act_prob'] = 0.1
      elif DG[e[0]][e[1]]['act_prob'] > 1:
        raise Exception("edge activation probability:", \
            DG[e[0]][e[1]]['act_prob'], "cannot be larger than 1")

  # perform diffusion
  A = copy.deepcopy(seeds)  # prevent side effect
  if steps <= 0:
    # perform diffusion until no more nodes can be activated
    return _diffuse_all(DG, A)
  # perform diffusion for at most "steps" rounds
  return _diffuse_k_rounds(DG, A, steps)

def _diffuse_all(G, A):
  tried_edges = set()
  layer_i_nodes = [ ]
  layer_i_nodes.append([i for i in A])  # prevent side effect
  while True:
    len_old = len(A)
    (A, activated_nodes_of_this_round, cur_tried_edges) = \
        _diffuse_one_round(G, A, tried_edges)
    layer_i_nodes.append(activated_nodes_of_this_round)
    tried_edges = tried_edges.union(cur_tried_edges)
    if len(A) == len_old:
      break
  return layer_i_nodes

def _diffuse_k_rounds(G, A, steps):
  tried_edges = set()
  layer_i_nodes = [ ]
  layer_i_nodes.append([i for i in A])
  while steps > 0 and len(A) < len(G):
    len_old = len(A)
    (A, activated_nodes_of_this_round, cur_tried_edges) = \
        _diffuse_one_round(G, A, tried_edges)
    layer_i_nodes.append(activated_nodes_of_this_round)
    tried_edges = tried_edges.union(cur_tried_edges)
    if len(A) == len_old:
      break
    steps -= 1
  return layer_i_nodes

def _diffuse_one_round(G, A, tried_edges):
  activated_nodes_of_this_round = set()
  cur_tried_edges = set()
  for s in A:
    for nb in G.successors(s):
      if nb in A or (s, nb) in tried_edges or (s, nb) in cur_tried_edges:
        continue
      if _prop_success(G, s, nb):
        activated_nodes_of_this_round.add(nb)
      cur_tried_edges.add((s, nb))
  activated_nodes_of_this_round = list(activated_nodes_of_this_round)
  A.extend(activated_nodes_of_this_round)
  return A, activated_nodes_of_this_round, cur_tried_edges

def _prop_success(G, src, dest):
  return random.random() <= G[src][dest]['act_prob']



# def vectorized_IC(A, nodes, seed):
#
#
#   infected_status = np.zeros(len(nodes))
#
#   # status list
#   UNINFECTED, INFECTED, REMOVED = 0, 1, 2
#
#   infected_status[seed] = INFECTED
#   infected_nodes = [seed.copy()]
#
#   while True:
#
#     current_active = np.where(infected_status == INFECTED)[0]
#     infected_nodes.append(current_active)
#
#     active_prob = A[current_active].toarray()
#
#     # print(active_prob)
#
#     next_layer = np.random.binomial(1, active_prob)
#
#     # print(next_layer)
#
#     # next_infected = np.where((next_layer == 1).any(axis=0))[0]
#
#     next_infected = next_layer.sum(0) > 0  # boolean array. True if they are infected
#
#     # print(next_infected)
#
#     next_infected = next_infected * (infected_status != REMOVED)
#
#     # print(next_infected)
#
#     # next_infected = next_infected[np.where(infected_status==2)]
#
#     infected_status[current_active] = REMOVED
#
#     infected_status[next_infected] = INFECTED
#
#     # print(infected_status)
#
#     if next_infected.sum() == 0:
#       break
#
#
#
#   return sum(infected_status == REMOVED), infected_nodes


def vectorized_IC(A, nodes, seed):
  infected_status = np.zeros(len(nodes))

  # status list

  UNINFECTED, INFECTED, REMOVED = 0, 1, 2

  infected_status[seed] = INFECTED

  infected_nodes = [seed.copy()]

  current_active = seed

  while True:

    active_prob = A[current_active].toarray()

    # print(active_prob)

    # find uninfected neighbors

    neighbors = (active_prob.sum(0) > 0) * (infected_status == UNINFECTED)

    next_layer = np.random.binomial(1, active_prob)

    # print(next_layer)

    # next_infected = np.where((next_layer == 1).any(axis=0))[0]

    next_infected = (next_layer.sum(0) > 0) * neighbors  # boolean array. True if they are infected


    # update status
    infected_status[neighbors] = REMOVED  # indexing using boolean array

    infected_status[current_active] = REMOVED  # indexing using list of indices

    infected_status[next_infected] = INFECTED  # indexing using boolean array

    # update current active
    current_active = np.where(infected_status == INFECTED)[0]

    infected_nodes.append(current_active)
    # print(infected_status)

    if next_infected.sum() == 0:
      break

  return None, infected_nodes


if __name__== '__main__':



  import pickle
  import time







  with open('../../k_submodular/influence_maximization/diggs/diggs.pkl', 'rb') as f:
    G = pickle.load(f)

  # with open('../../k_submodular/influence_maximization/diggs/diggs_active_users.pkl', 'rb') as f:
  #     active_users = pickle.load(f)
  users = G.nodes()


  # weight the graph
  for u, v in G.edges:
    G[u][v]['weight'] = G[u][v][f'k_{0}']

  A = nx.adjacency_matrix(G, nodelist=sorted(G.nodes))

  seed_set = list(users)[:100]
  print(seed_set)
  n_infected = []
  total_time = []
  for i in range(100):
    start_time = time.time()
    count, infected_nodes = vectorized_IC(A, G.nodes, seed_set)
    infected_nodes = set([j for i in infected_nodes for j in i])
    n_infected.append(len(infected_nodes))
    print(len(infected_nodes), sorted(infected_nodes))


    # assert count == len(infected_nodes)

    end_time = time.time()

    total_time.append(end_time - start_time)

  print(f'Total time {np.mean(total_time)}')
  print(f'#Infected {np.mean(n_infected)}')






  with open('../../k_submodular/influence_maximization/diggs/diggs.pkl', 'rb') as f:
    G = pickle.load(f)

  # with open('../../k_submodular/influence_maximization/diggs/diggs_active_users.pkl', 'rb') as f:
  #     active_users = pickle.load(f)
  users = G.nodes()


  # weight the graph
  for u, v in G.edges:
    G[u][v]['act_prob'] = G[u][v][f'k_{0}']


  seed_set = list(users)[:100]
  print(seed_set)
  n_infected = []
  total_time = []
  for i in range(100):
    start_time = time.time()
    infected_nodes = independent_cascade(G, seed_set, copy_graph=False)
    infected_nodes = set([j for i in infected_nodes for j in i])
    n_infected.append(len(infected_nodes))
    print(len(infected_nodes), sorted(infected_nodes))


    end_time = time.time()

    total_time.append(end_time - start_time)

  print(f'Total time {np.mean(total_time)}')
  print(f'#Infected {np.mean(n_infected)}')

