
"""
`sing` as in the singleton design pattern. See this page on "How do I share global variables across modules?" from the python docs:
  https://docs.python.org/3/faq/programming.html#id11

Nothing in this file is initialized because we want it to be set manually by whatever loading or init code gets run.
"""
from dreamcoder.matt.util import *
import torch.nn as nn
import torch
import traceback
import functools
from torch.utils.tensorboard import SummaryWriter
import shutil
from mlb.mail import email_me,text_me

class Sing(Saveable):
  no_save = ('w',)
  def __init__(self) -> None:
    pass
  def from_cfg(self, cfg):
    """
    note that this MUST modify sing inplace, it cant be a staticmethod
    bc otherwise when other modules do `from matt.sing import sing` theyll
    get a different copy if we ever reassign what sing.sing is. So it must be inplace.
    (i tested this).
    """

    if cfg.mode in ('train','profile','inspect','test'):
      if not cfg.load:
        ###########################################
        ### * MAKE NEW SING INCLUDING A MODEL * ###
        ###########################################

        if cfg.mode == 'test':
          raise ValueError("can't do mode=test without a file to load from")

        self.cfg = cfg

        """
        - sing.py gets used by everyone, so for simplicity we make sing do the imports within its own functions
        - for the record, we consider util.py to be used even more so it has to import sing within its own functions
        """
        from dreamcoder.matt.train import TrainState
        from dreamcoder import models,loader

        self.train_state = TrainState(cfg)
        self.cwd = cwd_path()
        init_paths()
        self.name = f'{cfg.job_name}.{cfg.run_name}'
        self.device = torch.device(cfg.device)
        self.stats = Stats()

        self.taskloader = {
          'deepcoder':loader.DeepcoderTaskloader
        }[self.cfg.data.type](train=True,valid=True)

        self.g = self.taskloader.g

        self.model = {
          'mbas': models.MBAS,
          'dc': models.Deepcoder, # todo
          'rb': models.Robustfill, # todo
        }[cfg.model.type]()

        self.model.to(self.device)
        self.set_tensorboard(self.name)
      else:
        ############################################
        ### * LOAD OLD SING CONTAINING A MODEL * ###
        ############################################
        overrided = [arg.split('=')[0] for arg in sys.argv[1:]]
        device = torch.device(cfg.device) if 'device' in overrided else None
        # in these cases cfg.load points to a Sing file

        paths = outputs_search(sing.cfg.load, ext='sing')
        if len(paths) == 0:
            red(f'Error: cfg.load={sing.cfg.load} doesnt match any files')
            sys.exit(1)
        if len(paths) > 1:
            red(f'Error: cfg.load={sing.cfg.load} matches more than one file')
            red(f'Matched files:')
            for p in paths:
                red(f'\t{p}')
            sys.exit(1)
        [path] = paths

        _sing = torch.load(path,map_location=device) # `None` means stay on original device
        self.clone_from(_sing) # will even copy over stuff like SummaryWriter object so no need for post_load()
        del _sing
        if device is not None:
          self.device = device # override sings device indicator used in various places
        self.apply_overrides(overrided,cfg)
        print(f"chdir to {self.cwd}")
        os.chdir(self.cwd)
        self.set_tensorboard(self.name)
    elif cfg.mode in ('plot','testgen','cmd'):
      ######################################################################
      ### * BARE BONES SING: NO TRAIN_STATE, NO MODEL, NO LOADERS, ETC * ###
      ######################################################################
      self.cfg = cfg
    else:
      raise ValueError(f"mode={cfg.mode} is not a valid mode")

   
  def save(self, name):
      path = with_ext(saves_path() / name, 'sing')
      print(f"saving Sing to {path}...")
      torch.save(self, f'{path}.tmp')
      shutil.move(f'{path}.tmp',path)
      print("done")
  def post_load(self):
    """
    we should not set_tensorboard() here otherwise when we torch.load
    a diff sing itll try to init a tensorboard in our location before
    we've chdired into a better place
    """
    pass
  def set_tensorboard(self,log_dir):
    print("intializing tensorboard")
    self.w = SummaryWriter(
        log_dir=self.name,
        max_queue=1,
    )
    print("initialized writer for", self.name)
  def which(self, no_yaml=False):
    return which(self.cfg,no_yaml)
  def yaml(self):
    return yaml(self.cfg)
  def tb_scalar(self, plot_name, val, j=None):
    """
    Best way to write a scalar to tensorboard.
     * feed in `j=` to override it otherwise it'll use `sing.s.j`
     * include a '/' in the plot_name like 'Validation/MyModel' to override
      * the default behavior where it assumes you want 'Validation' to mean
      * 'Validation/{cls_name(sing.model)}'
    """

    if '/' not in plot_name:
      plot_name = f'{plot_name}/{cls_name(sing.model)}'

    if j is None:
      j = sing.train_state.j
    
    self.w.add_scalar(plot_name, val, j)
    self.w.flush()
  def tb_plot(self, plot_name, fig, j=None):
    """
    Best way to write a plot to tensorboard.
     * feed in `j=` to override it otherwise it'll use `sing.s.j`
     * include a '/' in the plot_name like 'Validation/MyModel' to override
      * the default behavior where it assumes you want 'Validation' to mean
      * 'Validation/{cls_name(sing.model)}'
    """

    if '/' not in plot_name:
      plot_name = f'{plot_name}/{cls_name(sing.model)}'

    if j is None:
      j = sing.train_state.j
    
    self.w.add_scalar(plot_name, val, j)
    self.w.flush()
    
    



class Stats:
  """
  This is what `sing.stats` is.
  Used for stuff like tracking amount of concrete evaluation that happens
  or whatever else a model might want. model.__init__ should modify `sing.stats`
  for example `sing.stats.concrete_count=0` then other places in the codebase
  can increment that value.
  """
  def print_stats(self):
    print("Stats:")
    for k,v in self.__dict__.items():
      if callable(v):
        v = v(self)
      print(f'\t{k}: {v}')

# note we must never overwrite this Sing. We should never do `matt.sing.sing = ...` 
# because then it would only overwrite the local version and the version imported by other modules
# would stay as the old verison. I tested this.
sing = Sing()