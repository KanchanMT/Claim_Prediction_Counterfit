from traitlets.traitlets import default
import cmd2
import argparse
import re
import math

from typing import Any, List
from cmd2.table_creator import Column, SimpleTable, HorizontalAlignment

from collections import namedtuple
from counterfit.core.state import CFState
from counterfit.core import utils

parser = argparse.ArgumentParser()
parser.add_argument("what", nargs="*", help="param1=val1 param2=val2")


@cmd2.with_argparser(parser)
@cmd2.with_category("Counterfit Commands")
def do_set(self, args):
    """Set parameters of the active attack on the active target using param1=val1 param2=val2 notation.
    This command replaces built-in "set" command, which is renamed to "setg".
    """

    if not CFState.get_instance().active_target:
        self.pwarning('\n [!] No active target. Try "setg" for setting global arguments.\n')
        return

    if not CFState.get_instance().active_target.active_attack:
        self.pwarning('\n [!] No active attack. Try "use <attack>".\n')
        return

    # 'set' with no options shows current variables, similar to "show options"
    if not args.what:
        self.pwarning('\n [!] No arguments specified.  Try "set <param>=<value>".\n')

    # create default params struct
    default_params = {k: v for k, v in CFState.get_instance().active_target.active_attack.default.items()}
    default_params["sample_index"] = 0
    default_params["target_class"] = 0

    # get the type for appropriate typecasting for parsing
    type_dict = {k: type(v) for k, v in default_params.items()}

    # create structure to ensure all params are present and ordered properly. Defaults to current params to prevent over writing with default values
    params_struct = namedtuple(
        "params",
        list(default_params.keys()),
        defaults=list(default_params.values())
    )

    # ensure all current params exist and are ordered correctly
    default_params = params_struct(**default_params)._asdict()

    # parse parameters and new values from the args
    try:
        params_to_update = re.findall(r"(\w+)\s?=\s?([\w\.]+)", " ".join(args.what))
        # parse for rvalue=`lvalue`, where anything inside `` is an acceptable string
        params_to_update.extend(re.findall(r"(\w+)\s?=\s?(`.*`)", " ".join(args.what)))

    except:
        self.pwarning("\n [!] Failed to parse arguments.\n")
        return

    # parsing special cases
    for i, v in enumerate(params_to_update):
        # allow python eval with `` block in the rvalue
        if v[0] == 'sample_index':
            try:
                val = int(v[1])
            except:
                val = utils.parse_special_string_w_eval(v[1])
            # val = utils.parse_special_string_w_eval(v[1])
            params_to_update[i] = (v[0], val)
            type_dict[v[0]] = type(val)

        # convert string "True"/"true" and "False"/"false" to boolean
        if type(default_params.get(v[0], None)) is bool:
            if v[1].lower() == "true":
                val = True
            elif v[1].lower() == "false":
                val = False
            else:
                val = bool(int(v[1]))
            params_to_update[i] = (v[0], val)

        # convert "inf" to math.inf, can also do this as `float("inf")`
        if v[1].strip().lower == "inf":
            params_to_update[i] = (v[0], math.inf)
            type_dict[v[0]] = float

    # create current params struct
    current_params = {k: v for k, v in CFState.get_instance().active_target.active_attack.parameters.items()}
    current_params["sample_index"] = CFState.get_instance().active_target.active_attack.sample_index
    current_params["target_class"] = CFState.get_instance().active_target.active_attack.target_class

    # ensure all current params exist and are ordered correctly
    current_params = params_struct(**current_params)._asdict()

    # create new params struct using current (or default) values where no new values are spec'd
    casted_params = {i[0]: type_dict[i[0]](i[1]) for i in params_to_update}
    updated_dict = dict(current_params, **casted_params)
    new_params = params_struct(**updated_dict)

    # separate target_class and sample_index from struct and update the relevant values
    CFState.get_instance().active_target.active_attack.parameters = {
        k: v for k, v in zip(new_params._fields[:-2], new_params[:-2])
    }
    CFState.get_instance().active_target.active_attack.sample_index = new_params.sample_index
    CFState.get_instance().active_target.active_attack.target_class = new_params.target_class

    # print info
    print_new_params = new_params._asdict() 

    columns: List[Column] = list()
    data_list: List[List[Any]] = list()
    columns.append(Column("Attack Parameter (type)", width=25, header_horiz_align=HorizontalAlignment.LEFT,data_horiz_align=HorizontalAlignment.RIGHT))
    columns.append(Column("Default", width=12, header_horiz_align=HorizontalAlignment.CENTER,data_horiz_align=HorizontalAlignment.LEFT))
    columns.append(Column("Previous", width=12, header_horiz_align=HorizontalAlignment.CENTER,data_horiz_align=HorizontalAlignment.LEFT))
    columns.append(Column("New", width=12, header_horiz_align=HorizontalAlignment.CENTER,data_horiz_align=HorizontalAlignment.LEFT))

    for k, default_value in default_params.items():
        param = f"{k} ({str(type(default_value).__name__)})"
        previous_value = current_params.get(k, "")
        new_value = print_new_params.get(k, "")
        if new_value != previous_value:
            data_list.append([param, str(default_value), str(previous_value), str(new_value)])

        else:
            data_list.append([param, str(default_value), str(previous_value), ""])

    st = SimpleTable(columns)
    print()
    print(st.generate_table(data_list, row_spacing=0))
    print()
