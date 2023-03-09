import os, sys;
import pickle

sys.path.append(os.path.dirname('../'))
sys.path.append(os.path.dirname('../influence_maximization'))
import argparse

from multiprocessing import Pool
import numpy as np
import networkx
import pandas as pd
import matplotlib.pyplot as plt

import ohsaka
import threshold_algorithm

import independent_cascade


plt.rcParams['figure.figsize'] = [10,8]
plt.rc('font', size = 30)
plt.rc('legend', fontsize = 22)



def prepare_network(file, out_degrees=50):
    with open('./facebook_louvain_subgraph.pkl', 'rb') as f:
        network = pickle.load(f)

    active_nodes = []

    for n in network.nodes:
        d = network.out_degree(n)
        if d >= out_degrees:    # ~ 20 active nodes
            active_nodes.append(n)

    # to directed
    network = network.to_directed()
    return network, active_nodes


# TODO CHECK randomness is consistent
def create_K_networks(network, K):
    import random
    random.seed(1000)


    K_networks = [network.copy() for i in range(K)]

    for u, v in network.edges:

        # generate probs
        probs = [(i + 1) / (K * network.in_degree(v)) for i in range(K)]
        random.shuffle(probs)

        # weight graphs
        for i in range(K):
            K_networks[i][u][v]['act_prob'] = probs[i]

    print(len(K_networks))
    return K_networks




class Experiment:
    def __init__(self,
                 B_total,
                 B_i,
                 topics,  # topic ids to spread,
                 tolerance=None,
                 file='../../notebooks/facebook_ego.txt',
                 n_mc=50,
                 algorithm=None,
                 n_jobs=5

                 ):

        assert len(topics) == len(B_i), "#topics should be equal to the items to be selected"

        self.topics = topics # item id
        self.network, self.active_nodes = prepare_network(file)

        self._initialize_weighted_networks()

        self.n = len(self.active_nodes)
        print(f'Using {self.n} active users ')
        self.B_total = B_total # total budget
        self.B_i = B_i

        self.tolerance = tolerance
        self.n_mc = n_mc
        self.n_jobs = n_jobs

        print(f'Using {self.n_jobs} jobs, n_mc {self.n_mc}')


        # initialize algorithm
        if self.tolerance is not None:
            self.algorithms = [
                algorithm(self.n,
                    self.B_total,
                    self.B_i,
                    self.value_function,tolerance=t) for t in self.tolerance]
        else:
            self.algorithms = [algorithm(self.n,
                self.B_total,
                self.B_i,
                self.value_function)]




    def _initialize_weighted_networks(self):
        # load facebook network
        self.K_networks = create_K_networks(self.network, len(self.topics))



    def value_function(self, seed_set, n_mc=None):
        n_mc = n_mc or self.n_mc
        infected_nodes = {i:[] for i in range(n_mc)}
        print(seed_set)
        for topic_idx, topic in enumerate(self.topics):

            # filter list of users by topic(item)
            # Translate the values
            seed_t = [self.active_nodes[location_idx] for item_idx, location_idx in seed_set if item_idx == topic_idx]

            if seed_t:
                global ic_runner
                def ic_runner(t):
                    layers = independent_cascade.independent_cascade(self.K_networks[topic_idx], list(set(seed_t)))
                    infected_nodes_ = [i for l in layers for i in l]
                    return infected_nodes_

                with Pool(self.n_jobs) as p:
                    nodes = p.map(ic_runner, range(n_mc))
                    for i, n in enumerate(nodes):
                        infected_nodes[i].extend(n)

        # Aggregate infected_nodes over MC runs
        infected_nodes = np.mean([len(set(lst)) for lst in list(infected_nodes.values())])


        return infected_nodes


    def run(self):
        for alg in self.algorithms:
            alg.run()


    def final_run(self, S_list, n_mc=200):
        """
        Parameters
        ----------
        S_list list of selected values
        Returns a dictionary with the evaluations of S on corresponding algorithms
        ------
        """
        assert len(S_list) == len(self.algorithms), 'Number of algorithms and seed set do not match'
        final_vals = []
        for S in S_list:
            final_vals.append(self.value_function(S, n_mc=n_mc))

        return final_vals



    @property
    def results(self):
        return [{
            'alg': alg.name,
            'B_total': alg.B_total,
            'B_i': alg.B_i,
            'n_evals': alg.n_evaluations,
            'function_value': alg.current_value,
            'S': alg.S,
            'tolerance': self.tolerance[i] if self.tolerance is not None else None
        } for i, alg in enumerate(self.algorithms)]




if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Experiment runner')
    parser.add_argument('--mode', action='store', type=str, default='plot', choices=['run', 'plot', 'final'])
    parser.add_argument('--B', action='store', type=int, default=[ 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], nargs='+') # individual size
    parser.add_argument('--n-jobs', action='store', type=int, default=10)
    parser.add_argument('--n-mc', action='store', type=int, default=None)
    parser.add_argument('--tolerance', action='store', type=float, default=[0.1, 0.2], nargs='+') # TODO; update this
    parser.add_argument('--output', action='store', type=str, required=False)
    parser.add_argument('--alg', action='store', type=str, default=None,
                        choices=['KGreedyIndividualSizeConstrained', 'KStochasticGreedyIndividualSizeConstrained', 'ThresholdGreedyIndividualSizeConstrained'])

    args = parser.parse_args()

    mode = args.mode

    n_jobs = args.n_jobs
    tolerance_vals = args.tolerance
    n_mc = args.n_mc or 100
    n_mc_final = 500
    # topics = range(1, 9)  # k=8
    topics = range(1, 5)  # k=4
    B_totals = args.B
    B_totals = [B * len(topics) for B in B_totals ]

    print(f'Using Tolerance vals {tolerance_vals}, n_mc {n_mc}')

    # prepare directories
    output_dir = './output'
    os.makedirs(output_dir, exist_ok=True)

    alg_mappings = {
        'KGreedyIndividualSizeConstrained': [ohsaka.KGreedyIndividualSizeConstrained],
        'KStochasticGreedyIndividualSizeConstrained': [ohsaka.KStochasticGreedyIndividualSizeConstrained],
        'ThresholdGreedyIndividualSizeConstrained': [threshold_algorithm.ThresholdGreedyIndividualSizeConstrained]
    }

    algorithms = [
        ohsaka.KGreedyIndividualSizeConstrained,
        ohsaka.KStochasticGreedyIndividualSizeConstrained,
        threshold_algorithm.ThresholdGreedyIndividualSizeConstrained
    ]

    if args.alg:
        algorithms = alg_mappings[args.alg]

    if mode == 'run':
        for alg in algorithms:
            for B_total in B_totals:
                print(f'Running experiment for {alg} with budget {B_total}')
                print(f'Using topics {topics}')
                exp = Experiment(
                    B_total=B_total,
                    B_i=[B_total//len(topics)  for _ in topics],
                    topics=topics,
                    algorithm=alg,
                    tolerance= tolerance_vals[:1] if 'Threshold' in alg.__name__ else None,
                    n_jobs=n_jobs,
                    n_mc=n_mc
                )

                exp.run()

                # save file
                if 'Threshold' in alg.__name__:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_{tolerance_vals[0]}.pkl', 'wb') as f:
                        pickle.dump(exp.results, f)
                else:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_.pkl', 'wb') as f:
                        pickle.dump(exp.results, f)
    elif mode == 'final':
        for alg in algorithms:
            for B_total in B_totals:
                # look at pickles
                if 'Threshold' in alg.__name__:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_{tolerance_vals[0]}.pkl', 'rb') as f:
                        results = pickle.load(f)
                else:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_.pkl', 'rb') as f:
                        results = pickle.load(f)

                if results[0].get('final_function_value', None):
                    print('Already calculated ')
                    continue

                print(f'Running final run for {alg} with budget {B_total}')
                print(f'Using topics {topics}')
                exp = Experiment(
                    B_total=B_total,
                    B_i=[B_total//len(topics)  for _ in topics],
                    topics=topics,
                    algorithm=alg,
                    tolerance= tolerance_vals[:1] if 'Threshold' in alg.__name__ else None,
                    n_jobs=n_jobs,
                    n_mc=n_mc
                )

                final_vals = exp.final_run([r['S'] for r in results], n_mc=n_mc_final)
                for k, r in enumerate(results):
                    r['final_function_value'] = final_vals[k]


                # update pickles
                if 'Threshold' in alg.__name__:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_{tolerance_vals[0]}.pkl', 'wb') as f:
                        pickle.dump(results, f)
                else:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_.pkl', 'wb') as f:
                        pickle.dump(results, f)



    elif mode == 'plot':
        # load the files
        function_values = {}
        n_evaluations = {}

        algs = []

        for alg in algorithms:
            if 'Threshold' in alg.__name__:
                for t in tolerance_vals:
                    name = alg.name + f'($\epsilon$={t})'
                    function_values[name] = []
                    n_evaluations[name] = []
                    algs.append(alg)
            else:
                function_values[alg.name] = []
                n_evaluations[alg.name] = []
                algs.append(alg)

            for B_total in B_totals:
                if 'Threshold' in alg.__name__:
                    results = []
                    for t_val in tolerance_vals:
                        with open(f'{output_dir}/{alg.__name__}__{B_total}_{t_val}.pkl', 'rb') as f:
                            results.extend(pickle.load(f))
                else:
                    with open(f'{output_dir}/{alg.__name__}__{B_total}_.pkl', 'rb') as f:
                        results = pickle.load(f)

                # if type(results) == dict: results = [results]

                for i, r in enumerate(results):
                    if 'Threshold' in alg.__name__:
                        name = alg.name + f'($\epsilon$={tolerance_vals[i]})'
                        function_values[name].append(r.get('final_function_value', r['function_value']))
                        n_evaluations[name].append(r['n_evals'])
                    else:

                        function_values[alg.name].append(r.get('final_function_value', r['function_value']))
                        n_evaluations[alg.name].append(r['n_evals'])


        marker_types = ['o', 'v', '*', 'D', 's']
        for i, key in enumerate(function_values.keys()):
            plt.plot(range(len(B_totals)), function_values[key], label=key, marker=marker_types[i], markersize=12)
        plt.xticks(range(len(B_totals)), [B_total//len(topics)  for B_total in B_totals])
        plt.legend()
        plt.ylabel('Influence Spread')
        plt.xlabel('Value of b')
        plt.grid(axis='both')
        plt.savefig(f'{output_dir}/IS-influence-n51-k4.png', dpi=300, bbox_inches='tight')
        # plt.savefig(f'{output_dir}/IS-influence-n21-k8.png', dpi=300, bbox_inches='tight')
        plt.show()
        plt.figure()

        for i, key in enumerate(function_values.keys()):
            plt.plot(range(len(B_totals)), n_evaluations[key], label=key, marker=marker_types[i], markersize=12)

            plt.xticks(range(len(B_totals)), [B_total//len(topics)  for B_total in B_totals])

        plt.ylabel('Function Evaluations')
        plt.xlabel('Value of b')

        plt.grid(axis='both')
        plt.legend()
        # plt.savefig(f'{output_dir}/IS-eval-n21-k8.png', dpi=300, bbox_inches='tight')
        plt.savefig(f'{output_dir}/IS-eval-n51-k4.png', dpi=300, bbox_inches='tight')
        plt.show()
        plt.figure()