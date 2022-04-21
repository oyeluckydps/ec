# a sloppy approach to observational equivalence
# runs free variables on random inputs
import random
import itertools

from dreamcoder.frontier import *
from dreamcoder.program import *
from dreamcoder.type import *
from dreamcoder.utilities import *
import dreamcoder as dc


class Sloppy():
    def __init__(self, inputs, n=6, sound=True, continuationType=None):
        self.continuationType=continuationType
        self.sound = sound
        self.inputs = inputs
        self.next_symbol = 0
        self._test_inputs = {}
        self.n=n

    def unique_symbol(self):
        self.next_symbol += 1
        return self.next_symbol

    def sound_signature(self, expression, tp, arguments):
        if self.inputs is None: 
            raise Exception("No example inputs provided in Sloppy!")

        # eprint()
        # eprint(expression, tp, arguments)
        # for i in expression.freeVariables():
        #     eprint("free ", i, arguments[i])
            
        
        outputs = []
        for i in expression.freeVariables():
            #illegal?
            if self.continuationType is None and i < len(arguments) - len(self.inputs[0]) or\
               (self.continuationType is not None and self.continuationType!=arguments[i]):
                #eprint("invalid")
                return self.unique_symbol()
        #eprint("good work")

        for test_input in self.inputs:
            if self.continuationType is None:
                environment = [None]*(len(arguments) - len(test_input))+list(reversed(test_input))
            if self.continuationType is not None:
                environment = [None]*len(arguments)
                continuation_value = None
                for argument_type, input_data in zip(arguments, test_input):
                    if argument_type == self.continuationType:
                        continuation_value = input_data
                        break
                assert continuation_value is not None
                #eprint("continuation_value", continuation_value)
                
                for i in range(len(arguments)):
                    if arguments[i] == self.continuationType:
                        environment[i] = continuation_value
                
            try:
                o = expression.evaluate(environment)
            except Exception as e:
                # eprint("generated exception", e)
                o = None
            if o is None:
                outputs.append(None)
                continue
            try:
                outputs.append(self.value_to_key(o, tp))
                hash(outputs[-1])
            except:
                eprint(expression, tp, environment, o, test_input)
                assert False
        #eprint("output", tuple(outputs))
        if all(o is None for o in outputs):
            return None
        return tuple(outputs)

    def compute_signature(self, expression, tp, arguments):
        
        if self.sound: return self.sound_signature(expression, tp, arguments)
        
        outputs = []
        for test_input in self.test_inputs(arguments):
            try:
                o = expression.evaluate(test_input)
            except:
                o = None
            if o is None:
                outputs.append(None)
                continue
            try:
                outputs.append(self.value_to_key(o, tp))
            except:
                eprint(expression, tp, o, test_input)
                assert False
        if all(o is None for o in outputs):
            return None
        return tuple(outputs)

    def possible_values(self, tp):
        if str(tp) == "int":
            return random.choices(range(-10,0), k=n//2-2) +\
                random.choices(range(10), k=n//2-1) +\
                [-1,0,1]
        if str(tp) == "bool":
            return [False,True]
        if str(tp) == "real":
            return [random.random()*10-5 for _ in range(self.n) ]
        if str(tp) == "tsize":
            return [4]
        if str(tp) == "tcircuit":
            return [dc.domains.quantum_algorithms.primitives.no_op(4)]
        if str(tp) == "tcircuit_full":
            return [dc.domains.quantum_algorithms.primitives.f_no_op(4)]
        if isinstance(tp, TypeConstructor):
            if tp.name=="list":
                return [ [ random.choice(self.possible_values(tp.arguments[0]))
                           for _ in range(random.choice(range(4))) ]
                         for _ in range(self.n-1) ]+\
                             [[]]
            if tp.isArrow:
                assert False, "not supported function types for observational equivalents"
        assert False, f"unsupported type {tp}"
        

    def test_inputs(self, arguments):
        if tuple(arguments) in self._test_inputs:
            return self._test_inputs[tuple(arguments)]

        if self.inputs is not None:
            # drop the last arguments because they correspond to the inputs
            number_of_arguments = len(self.inputs[0])
            arguments = arguments[:-number_of_arguments]

        test_inputs=[]
        for sloppy in itertools.product(*(self.possible_values(a) for a in arguments)):
            if self.inputs is not None:
                for input_tuple in self.inputs:
                    test_inputs.append(list(sloppy) + list(reversed(input_tuple)))
            else:
                test_inputs.append(list(sloppy))
        test_inputs = random.sample(test_inputs, min(len(self.inputs),
                                                     len(test_inputs)))
        self._test_inputs[tuple(arguments)] = test_inputs
        # print(arguments, test_inputs)
        return test_inputs
    
    def value_to_key(self, value, output_type):
        if output_type == dc.domains.quantum_algorithms.primitives.tcircuit:
            # We need to check two things
            # Final position should be the same (otherwise we exclude all moving operations)
            # Generated unitary should be the same
            unitary = dc.domains.quantum_algorithms.primitives.state_circuit_to_mat(value)
            value = (tuple(value[0]), unitary.tobytes())
        elif output_type == dc.domains.quantum_algorithms.primitives.tcircuit_full:
            # Here we only need check the unitary
            # (as we don't move along the circuit and have no position)
            unitary = dc.domains.quantum_algorithms.primitives.full_circuit_to_mat(value)
            value = unitary.tobytes()

        elif str(output_type)=="tower":
            state, plan = value(dc.domains.tower.towerPrimitives.TowerState())
            value = (state.hand, state.orientation, tuple(plan))
        elif isinstance(output_type, TypeConstructor) and output_type.name=="list":
            value = tuple(self.value_to_key(v, output_type.arguments[0])
                          for v in value )
        
        return value

    
