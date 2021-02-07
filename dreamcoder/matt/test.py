import pathlib
from dreamcoder.matt.util import *
import sys
import torch

from dreamcoder.matt.sing import sing


def main():
    test = sing.cfg.test

    if test.out is None:
        test.out = f'{sing.cfg.time_start_filename}.{sing.cfg.job_name}.{sing.cfg.run_name}.res'
    
    if test.from_file is None:
        die('Error: missing argument test.from_file')
    
    # load tests
    path = with_ext(testgen_path() / test.from_file, 'tgen')
    if not path.exists():
        die(f'Error: cant find testgen file: {path}')
    tgen = torch.load(path)
    
    model_result = sing.model.search(tgen.fs, test.timeout, verbose=True)
    model_result.save(test.out)




def test_models(astars, test_tasks, g, timeout, verbose=True, scaffold=False):
    """
    `astars`: a list of one or more Astar objects
        These can be easily made with makeDeepcoderData.make_solver('astar',vhead,phead,maxDepth)
    `test_tasks`: a list of Tasks or FakeFrontiers to run search on
    `g`: Grammar passed to Astar.infer()
    `timeout`: the search timeout
    """
    test_scaffolds = None
    if len(test_tasks) > 0 and isinstance(test_tasks[0], FakeFrontier):
        if scaffold:
            test_scaffolds = [f.scaffold for f in test_tasks]
        test_tasks = [f.task for f in test_tasks]

    model_results = []
    for astar in astars:
        rec_model = None
        if hasattr(astar,'actual_solver') and astar.actual_solver is not None:
            assert isinstance(astar.owner.policyHead, DeepcoderListPolicyHead)
            rec_model = astar.owner.policyHead.rec_model
            astar = astar.actual_solver
            mlb.purple('[deepcoder model testing]')
        
        if isinstance(astar.owner.policyHead,SyntaxCheckingRobustFill):
            model_results.append(robustfill_search(astar.owner.policyHead, test_tasks, timeout))
            continue

        sing.to_optimize.eval()
        astar.owner.policyHead.eval()
        astar.owner.valueHead.eval()
        #name = f"{astar.owner.policyHead.__class__.__name__}_&&_{astar.owner.valueHead.__class__.__name__}"
        name = astar.owner.policyHead.cfg.name
        prefix = astar.owner.policyHead.cfg.prefix
        print(f"Testing: {name}")
        search_results = []
        search_failures = []
        likelihoodModel = AllOrNothingLikelihoodModel(timeout=0.01)
        for i,task in enumerate(test_tasks):
            if scaffold:
                starting_nodes = [test_scaffolds[i]]
            else:
                starting_nodes = None
            with torch.no_grad():

                if rec_model is not None:
                    rec_model.eval()
                    g = rec_model.grammarOfTask(task).untorch()
                    rec_model.train()
                fs, times, num_progs, solns = astar.infer(
                        g, 
                        [task],
                        likelihoodModel, 
                        timeout=timeout,
                        elapsedTime=0,
                        evaluationTimeout=0.01,
                        maximumFrontiers={task: 2},
                        CPUs=1,
                        starting_nodes=starting_nodes,
                    ) 
            solns = solns[task]
            times = times[task]
            if len(solns) > 0:
                assert len(solns) == 1 # i think this is true, I want it to be true lol
                soln = solns[0]
                search_results.append(soln)
                if verbose:
                    mlb.green(f"[{i+1}/{len(test_tasks)}] solved {task.name} with {len(solns)} solns in {times:.2f}s (searched {num_progs} programs)")
                    t,d,s = get_depth(solns[0].program)
                    print(f"\t-> [T{t}d{d}s{s}] {solns[0].program}")
            else:
                if verbose: mlb.red(f"[{i+1}/{len(test_tasks)}] failed to solve {task.name} (searched {num_progs} programs)")
                search_failures.append(num_progs)
        model_results.append(plot.ModelResult(prefix=prefix,name=name, cfg=astar.owner.policyHead.cfg, search_results=search_results, search_failures=search_failures, timeout=timeout))
        if verbose: mlb.blue(f'solved {len(search_results)}/{len(test_tasks)} tasks ({len(search_results)/len(test_tasks)*100:.1f}%)\n')
    return model_results


# def analyze_tasks(tasks):
#     requests = defaultdict(int)
#     for task in tasks:
#         task.request

def cfg_diff(train_cfg,test_cfg):
    mlb.magenta("Differences between train and test:")
    for key in set(test_cfg.keys()) | set(train_cfg.keys()):
        if key in ['threaded', 'num_templates', 'valid_frac', 'buf_size', 'repeat', 'print_data']:
            continue #ignore these
        if key not in test_cfg:
            mlb.yellow(f"warn: key not in test data config: {key}")
            continue
        elif key not in train_cfg:
            mlb.yellow(f"warn: key not in train data config: {key}")
            continue
        if test_cfg[key] != train_cfg[key]:
            mlb.magenta(mlb.mk_bold(f"\t{key=} {train_cfg[key]=} {test_cfg[key]=}"))
