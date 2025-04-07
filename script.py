from pycaliper.per import *

from pycaliper.pycmanager import PYCArgs, setup_all
from pycaliper.synth.persynthesis import PERSynthesizer, IISStrategy, SeqStrategy, RandomStrategy, LLMStrategy, HoudiniSynthesizerJG, HoudiniSynthesizerConfig, HoudiniSynthesizerBTOR
from pycaliper.proofmanager import mk_btordesign
from pycaliper.pycconfig import DesignConfig
from pycaliper.jginterface.jgdesign import JGDesign
from pycaliper.verif.jgverifier import JGVerifier2Trace
from pycaliper.verif.btorverifier import BTORVerifier2Trace


from cacheline_nru import cacheline_nru

# Log to a debug file with overwriting
logging.basicConfig(filename="debug.log", level=logging.DEBUG, filemode="w")

# Which solver backend to use
BTOR_BACKEND = 0
JG_BACKEND = 1

def dawg_synth(strat: IISStrategy, fuelbudget: int, stepbudget: int, retries: int, k: int = 2, backend: int = BTOR_BACKEND):
    
    params = {"MODE": 0, "k": k}
    module = cacheline_nru(**params).instantiate()
    
    if backend == JG_BACKEND:
        args = PYCArgs(jgcpath="config_nru.json")
        is_conn, pyconfig, tmgr = setup_all(args)
        assert is_conn, "Connection to Jasper failed!"

        synthesizer = HoudiniSynthesizerJG()
        finalmod, stats = synthesizer.synthesize(module, 
                                                 JGDesign("cacheline_nru", pyconfig), 
                                                 pyconfig.dc,
                                                 strat,
            HoudiniSynthesizerConfig(fuelbudget=fuelbudget, 
                                     stepbudget=stepbudget, retries=retries))
    else:
        args = PYCArgs(jgcpath="")
        is_conn, pyconfig, tmgr = setup_all(args)
    
        synthesizer = HoudiniSynthesizerBTOR()
        finalmod, stats = synthesizer.synthesize(module,
            mk_btordesign("cacheline_nru", "DAWG/cacheline_nru_miter.btor"),
            DesignConfig(), 
            strat,
            HoudiniSynthesizerConfig(fuelbudget=fuelbudget, stepbudget=stepbudget, retries=retries))

    print(f"Synthesis stats: minfuel={stats.minfuel}, solvecalls={stats.solvecalls}, steps={stats.steps}, success={stats.success}")
    tmgr.save_spec(finalmod)
    tmgr.save()


def dawg_verif(k):
    args = PYCArgs(jgcpath="config_nru.json")
    is_conn, pyconfig, tmgr = setup_all(args)

    assert is_conn, "Connection to Jasper failed!"

    verifierjg = JGVerifier2Trace()
    verifierbtor = BTORVerifier2Trace()
    
    params = {"MODE": 0, "k": k}
    module = cacheline_nru(**params).instantiate()

    resbtor = verifierbtor.verify(module, 
                                      mk_btordesign("cacheline_nru", "DAWG/cacheline_nru_miter.btor"),
                                      DesignConfig())
    
    if not resbtor.verified:
        with open("trace.vcd", "w") as f:
            f.write(resbtor.model)

    resjg = verifierjg.verify(module, pyconfig)

    print(f"Verification result: {resbtor.verified} (BTOR), {resjg} (JG)")


if __name__ == "__main__":
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description="Synthesize the DAWG cache design")
    parser.add_argument("--fuelbudget", type=int, default=10, help="Fuel budget for synthesis")
    parser.add_argument("--stepbudget", type=int, default=10, help="Step budget for synthesis")
    parser.add_argument("--retries", type=int, default=10, help="Number of retries for synthesis")
    parser.add_argument("--strategy", type=str, default="seq", help="Synthesis strategy [seq | rand | llm]")
    parser.add_argument("--k", type=int, default=2, help="Number of ways in the cache")
    parser.add_argument("--solver", type=str, default="btor", help="Solver backend [btor | jg]")
    args = parser.parse_args()

    # Choose the synthesis strategy
    match args.strategy:
        case "seq":
            strat = SeqStrategy()
        case "rand":
            strat = RandomStrategy()
        case "llm":
            strat = LLMStrategy()
        case _:
            raise ValueError(f"Invalid strategy {args.strategy}")
        
    # Synthesize the design
    dawg_synth(strat, args.fuelbudget, args.stepbudget, args.retries, args.k, JG_BACKEND if args.solver == "jg" else BTOR_BACKEND)
