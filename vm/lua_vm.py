from __future__ import annotations

from vm.state import LuaState
from vm.operator import Operator


class LuaVM:
    @staticmethod
    def fetch(state: LuaState):
        return state.fetch()

    @staticmethod
    def execute(state: LuaState) -> bool:
        inst = LuaVM.fetch(state)
        if inst is None:
            return False
        op_name = inst.op_name()
        method = getattr(Operator, op_name, None)
        if method:
            # print(f"-{len(state.call_info)}- " + str(inst).ljust(40))
            method(inst, state)
            # print(
            #     f"-{len(state.call_info)}- "
            #     + ''.join(f"[{v}]" for v in state.stack)
            # )
        return True

    @staticmethod
    def get_rk(state: LuaState, rk: int):
        return state.get_rk(rk)
