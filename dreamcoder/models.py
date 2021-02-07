from dreamcoder.matt.util import *
import torch
from torch import nn
from dreamcoder.matt.sing import sing
from dreamcoder.pnode import PNode,PTask
from dreamcoder.Astar import astar_search
from dreamcoder import valueHead,policyHead
from dreamcoder.matt import plot
from dreamcoder import aux_models
from dreamcoder.likelihoodModel import AllOrNothingLikelihoodModel

class MBAS(nn.Module):
  def __init__(self):
    super().__init__()

    sing.stats.call_encode_known_ctx = 0
    sing.stats.call_encode_exwise = 0
    sing.stats.fn_called_concretely = 0
    sing.stats.fn_called_abstractly = 0
    sing.stats.cache_used = 0
    sing.stats.cache_not_used = 0
    sing.stats.cache_cleared = 0

    sing.stats.cache_hit_rate = cache_hit_rate
    sing.stats.concrete_rate = concrete_rate

    self.running_vloss = RunningFloat()
    self.running_ploss = RunningFloat()


    # add all submodules required by vhead and phead
    submodules = set()

    submodules |= {
      'repl': {aux_models.AbstractionFn, aux_models.AbstractTransformers, aux_models.AbstractComparer},
      'rnn': {aux_models.AbstractionFn, aux_models.ProgramRNN},
      'check_invalid': set(),
      'uniform': set(),
    }[sing.cfg.model.vhead]

    submodules |= {
      'repl': {aux_models.AbstractionFn, aux_models.AbstractTransformers, aux_models.AbstractComparer},
      'rnn': {aux_models.AbstractionFn, aux_models.ProgramRNN},
      'uniform': set(),
    }[sing.cfg.model.phead]

    for mod in submodules:
      # initialize submodules and assign as attributes to self
      name = {
        aux_models.AbstractionFn: 'abstraction_fn',
        aux_models.AbstractTransformers: 'abstract_transformers',
        aux_models.AbstractComparer: 'abstract_comparer',
        aux_models.ProgramRNN: 'program_rnn',
      }[mod]
      setattr(self,name,mod())

    # vhead and phead init

    self.vhead = {
      'repl': valueHead.ListREPLValueHead,
      'rnn': valueHead.RNNValueHead,
      'check_invalid': valueHead.InvalidIntermediatesValueHead,
      'uniform': valueHead.UniformValueHead,
    }[sing.cfg.model.vhead]()

    self.phead = {
      'repl': policyHead.ListREPLPolicyHead,
      'rnn': policyHead.RNNPolicyHead,
      'uniform': policyHead.UniformPolicyHead,
    }[sing.cfg.model.phead]()

    # init the optimizer
    self.optim = torch.optim.Adam(self.parameters(), lr=sing.cfg.optim.lr, eps=1e-3, amsgrad=True)

  def run_tests(self,fs):
    # fs are the validation frontiers for the record
    self.abstraction_fn.encoder.run_tests()
    # TODO run more tests here!

  def train_step(self,fs):
    assert len(fs) == 1
    [f] = fs
    self.train()
    self.zero_grad()

    vloss = self.vhead.train_loss(f.p, f.t)
    ploss = self.phead.train_loss(f.p, f.t)

    self.running_vloss.add(vloss)
    self.running_ploss.add(ploss)

    loss = vloss + ploss
    loss.backward()
    self.optim.step()
    return loss, None

  def print_every(self):
    sing.tb_scalar('PolicyLoss', self.running_ploss.avg())
    sing.tb_scalar('ValueLoss', self.running_ploss.avg())

    print(f'\tValueLoss {cls_name(self.vhead)} {self.running_vloss.avg()}')
    print(f'\tPolicyLoss {cls_name(self.phead)} {self.running_ploss.avg()}')

    self.running_ploss.reset()
    self.running_vloss.reset()

    sing.stats.print_stats()

  def valid_step(self,fs):
    self.eval()
    with torch.no_grad():
      running_loss = RunningFloat()
      running_vloss = RunningFloat()
      running_ploss = RunningFloat()
      for f in fs:
        vloss = self.vhead.train_loss(f.p,f.t)
        ploss = self.phead.train_loss(f.p,f.t)
        running_vloss.add(vloss)
        running_ploss.add(ploss)
        running_loss.add(vloss+ploss)
    
    sing.tb_scalar('ValidPolicyLoss', self.running_ploss.avg())
    sing.tb_scalar('ValidValueLoss', self.running_vloss.avg())

    to_print = f'\tValidValueLoss {cls_name(self.vhead)} {self.running_vloss.avg()}\n\tValidPolicyLoss {cls_name(self.phead)} {self.running_ploss.avg()}'

    return running_loss.avg(), to_print

  def search(self, fs, timeout, verbose=True):
    """
    Gets `solver` from sing.cfg.solver
    Note that AStar and SMC will also read their details from `sing.cfg.test` for
      stuff like no_resample
    """
    assert len(fs) > 0

    fs = [(PNode.from_dreamcoder(f.p,f.t), PTask(f.t)) for f in fs]

    # quick checks
    for (soln, task) in fs:
      assert soln.depth() <= sing.cfg.solver.max_depth
      if hasattr(sing.cfg.solver,'max_size'):
        assert soln.size() <= sing.cfg.solver.cfg.max_size

    search_tries = []
    self.eval()

    with torch.no_grad():
      for i,(true_soln,task) in enumerate(fs):

        # prep the task
        root = PNode.from_ptask(task)

        # run search
        if sing.cfg.solver.type == 'astar':
          search_try = astar_search(root, self.phead, self.vhead, timeout)
        elif sing.cfg.solver.type == 'smc':
          raise NotImplementedError
        else:
          raise TypeError

        search_tries.append(search_try)

        if verbose:
          if search_try.hit:
            green(f"[{i+1}/{len(fs)}] solved in {search_try.time:.2f}s (searched {search_try.nodes_expanded} programs)")
            print(f"\t-> found: [T?d{search_try.soln.depth()}s{search_try.soln.size()}] {search_try.soln}")
            print(f"\t-> orig:  [T?d{true_soln.depth()}s{true_soln.size()}] {true_soln}")
          else:
            red(f"[{i+1}/{len(fs)}] failed to solve {true_soln} (searched {search_try.nodes_expanded} programs)")

    # build final model result
    model_result = plot.ModelResult(search_tries,timeout)

    if verbose:
      blue(f'solved {len(model_result.hits)}/{len(fs)} tasks ({model_result.accuracy():.1f}%)\n')

    return model_result
    
class Deepcoder(nn.Module):
  pass # todo
class Robustfill(nn.Module):
  pass # todo



def concrete_rate(stats):
  try:
    return stats.fn_called_concretely / (stats.fn_called_concretely + stats.fn_called_abstractly)
  except ZeroDivisionError:
    return 0
def cache_hit_rate(stats):
  try:
    return stats.cache_used / (stats.cache_used + stats.cache_not_used)
  except ZeroDivisionError:
    return 0