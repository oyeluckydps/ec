
import numpy as np
import dreamcoder as dc
from dreamcoder.utilities import eprint
import qiskit as qk
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit,Aer
backend = Aer.get_backend('unitary_simulator')
    
class QuantumCircuitException(Exception):
    ...

# ------------------------------------------
# Transform a list of qubit operations into a unitary 
#

qiskit_full_op_names = lambda QT: {
    "eye": lambda q1: QT.circuit.id(q1),
    "hadamard": lambda q1: QT.circuit.h(q1),
    "cnot":  lambda q1,q2: QT.circuit.cnot(q1,q2),
    "swap": lambda q1,q2: QT.circuit.swap(q1,q2),
    "cz": lambda q1,q2: QT.circuit.cz(q1,q2),
}

eyes = {} #caching initial identity matrices
full_circuit_cache = {}
def circuit_to_mat(full_circuit):
    t_full_circuit = tuple(full_circuit)
    try:
        if t_full_circuit not in full_circuit_cache:
            n_qubit, op_list = full_circuit
            
            with QiskitTester(n_qubit) as QT:
                op_names = qiskit_full_op_names(QT)
                for op in op_list:
                    op_names[op[0]](*op[1:])
                
            full_circuit_cache[t_full_circuit] = QT.result
    except TypeError as e:
        ...
    return full_circuit_cache[t_full_circuit]


# ---------------------------------------------------------------------------------
# Transpiler configuration
from qiskit.transpiler.synthesis import solovay_kitaev
skd = solovay_kitaev.SolovayKitaevDecomposition()
basis_gates=['h',"cx",'t',"tdg"] 

## Qiskit implementation, which natively also includes plotting 
class QiskitTester():
    def __init__(self,n_qubits=None):
        self.n_qubits = n_qubits
        self.qreg_q = QuantumRegister(self.n_qubits, 'q')
        self.circuit = QuantumCircuit(self.qreg_q)
        
    def q(self,q_num):
        return self.n_qubits -1- q_num
    
    def __enter__(self):
        return self
    
    def get_result(self, circuit):
         return np.array(qk.execute(circuit, backend).result().get_unitary()).T
    
    def __exit__(self,*args, **kwargs):
        self.result = self.get_result(self.circuit)
        
    def __str__(self) -> str:
        return self.circuit.__str__()
        
    def check(self):
        # Checks that unitary code is consistent with what Qiskit would generate
        try:
            np.testing.assert_almost_equal(self.unitary_matrix,self.result, decimal=3)
            eprint("Code consistent with Qiskit")
        except AssertionError as e:
            eprint("-----------------------------------")
            eprint("ERROR: ")
            eprint(self.unitary_matrix)
            eprint(self.result)
            eprint(e)
            
    def get_transpiled(self, circuit):
        transpiled=qk.transpile(circuit, backend)
        circuit2 = pm.run(transpiled)
        discretized = skd(circuit2)
        return qk.transpile(discretized,backend, basis_gates)
    
    def transpile(self):
        return self.get_transpiled(self.circuit)
    

def print_circuit(full_circuit, filename=None):
    with QiskitTester(full_circuit) as QT:
        n_qubit, op_list = full_circuit
        op_names = qiskit_full_op_names(QT)
        for op in op_list:
            op_names[op[0]](*op[1:])
            
        # pip install pylatexenc for mpl draw
        QT.circuit.draw(output="mpl", filename=filename) if filename is not None else eprint(QT) 
        plt.show()
        


with QiskitTester(1) as QT:
    QT.circuit.t(0)
    QT.circuit.t(0)
qk.circuit.equivalence_library.StandardEquivalenceLibrary.add_equivalence(qk.circuit.library.SGate(),QT.circuit)

with QiskitTester(1) as QT:
    QT.circuit.tdg(0)
    QT.circuit.tdg(0)
qk.circuit.equivalence_library.StandardEquivalenceLibrary.add_equivalence(qk.circuit.library.SdgGate(),QT.circuit)

class ParametricSubstitution(qk.transpiler.TransformationPass):
    def run(self, dag):
        # iterate over all operations
        for node in dag.op_nodes():
            print(node.op.name, node.op.params)
            # if we hit a RYY or RZZ gate replace it
            
            if node.op.name in ["cp"]:
                replacement = QuantumCircuit(2)
                replacement.p(node.op.params[0]/2,0)
                replacement.cx(0,1)
                replacement.p(-node.op.params[0]/2,1)
                replacement.cx(0,1)
                replacement.p(node.op.params[0]/2,1)

                # replace the node with our new decomposition
                dag.substitute_node_with_dag(node, qk.converters.circuit_to_dag(replacement))
                                
            
            if node.op.name in ["p"] and node.op.params[0]==np.pi/2:

                # calculate the replacement
                replacement = QuantumCircuit(1)
                replacement.s([0])

                # replace the node with our new decomposition
                dag.substitute_node_with_dag(node, qk.converters.circuit_to_dag(replacement))
                
            elif node.op.name in ["p"] and node.op.params[0]==3*np.pi/2:
    
                # calculate the replacement
                replacement = QuantumCircuit(1)
                replacement.tdg([0])
                replacement.tdg([0])

                # replace the node with our new decomposition
                dag.substitute_node_with_dag(node, qk.converters.circuit_to_dag(replacement))
                               
            elif node.op.name in ["p"] and node.op.params[0]==5*np.pi/2:
        
                # calculate the replacement
                replacement = QuantumCircuit(1)
                replacement.t([0])
                replacement.t([0])

                # replace the node with our new decomposition
                dag.substitute_node_with_dag(node, qk.converters.circuit_to_dag(replacement))
                               
                               
        return dag
pm = qk.transpiler.PassManager()
pm.append(ParametricSubstitution())

# ------------------------------------------ End of Qiskit code

# ------------------------------------------
# Define functions for primitives (to act on circuits)
#
# tsize = dc.type.baseType("tsize")
tcircuit = dc.type.baseType("tcircuit")


# Control
def _repeat(n_times,body):
    if n_times <= 0:
        raise QuantumCircuitException("Invalid repetition number.")
    return   _repeat_help(n_times, body, body)

def _repeat_help(n_times, body, new_body):
    if n_times==1:
        return new_body
    return _repeat_help(n_times-1, body, lambda b: new_body(body(b)))




# ------------------------------------------
# Define FULL primitives
# 

# Arithmetics
p_0 = dc.program.Primitive("0",dc.type.tint,0)
p_inc = dc.program.Primitive("inc", dc.type.arrow(dc.type.tint, dc.type.tint), lambda x:x+1)
p_dec = dc.program.Primitive("dec", dc.type.arrow(dc.type.tint, dc.type.tint), lambda x:x-1)

## Full circuit [n_qubits, [ops]]
def no_op(n):
    return (n, ())

def get_n_qubits(old_circuit):
    return old_circuit[0]

def one_qubit_gate(old_circuit, qubit_1,operation_name):
    n_qubit, circuit = old_circuit
        
    if qubit_1<0 or qubit_1 >= n_qubit:
        raise QuantumCircuitException("Invalid selected qubit")
    
    circuit = circuit + ((operation_name, qubit_1),)
    return (n_qubit, circuit)

def two_qubit_gate(old_circuit, qubit_1, qubit_2, operation_name):
    # operation_name = "cnot" or some other gate name
    n_qubit, circuit = old_circuit
    
    if qubit_1<0 or qubit_1 >= n_qubit:
        raise QuantumCircuitException("Invalid selected qubit")
    
    if qubit_2<0 or qubit_2 >= n_qubit:
        raise QuantumCircuitException("Invalid selected qubit")
   
    if qubit_1 == qubit_2:
        raise QuantumCircuitException("Invalid selected qubit")
    
    circuit = circuit + ((operation_name, qubit_1, qubit_2),)
    return (n_qubit, circuit)

# Circuit primitives

p_size = dc.program.Primitive(name="size", 
                     ty=dc.type.arrow(tcircuit, dc.type.tint),
                     value=get_n_qubits)

p_hadamard = dc.program.Primitive(name="h", 
                     ty=dc.type.arrow(tcircuit, dc.type.tint, tcircuit),
                     value=dc.utilities.Curried(lambda old_circuit, qubit_1: one_qubit_gate(old_circuit, qubit_1, "hadamard")))

p_cnot = dc.program.Primitive(name="not", 
                     ty=dc.type.arrow(tcircuit, dc.type.tint, dc.type.tint,tcircuit),
                     value=dc.utilities.Curried(lambda old_circuit, qubit_1, qubit_2: two_qubit_gate(old_circuit, qubit_1, qubit_2, "cnot")))

p_swap = dc.program.Primitive(name="swap", 
                     ty=dc.type.arrow(tcircuit, dc.type.tint, dc.type.tint, tcircuit),
                     value=dc.utilities.Curried(lambda old_circuit, qubit_1, qubit_2: two_qubit_gate(old_circuit, qubit_1, qubit_2, "swap")))

# Control
p_iteration = dc.program.Primitive(name="rep", 
                     ty=dc.type.arrow(dc.type.tint, dc.type.arrow(tcircuit,tcircuit),  dc.type.arrow(tcircuit,tcircuit)),
                     value=dc.utilities.Curried(_repeat))


full_primitives = [
    #circuits
    p_hadamard,
    p_cnot,
    p_swap,
    #arithmetics
    p_0,
    p_inc,
    p_dec,
    p_size,
    # #control
    # fp_iteration
]

primitives = [
    #circuits
    p_hadamard,
    p_cnot,
    #arithmetics
    p_0,
    p_inc,
    p_dec,
    p_size,
    # #control
    # fp_iteration
]

# ------------------------------------------
# Define GRAMMAR
# 
full_grammar = dc.grammar.Grammar.uniform(full_primitives, continuationType=tcircuit)
grammar = dc.grammar.Grammar.uniform(primitives, continuationType=tcircuit)
            

# ------------------------------------------
# Function to execute algorithms (which are functions)
# Maybe it should return a function?
# 
def execute_quantum_algorithm(p, n_qubits, timeout=None):
    try:
        circuit =  dc.utilities.runWithTimeout(
            lambda: p.evaluate([])(no_op(n_qubits)),
            timeout=timeout
        )
        return circuit_to_mat(circuit)
    except dc.utilities.RunWithTimeout: return None
    except: return None
    
    
