"""Multi-agent traffic light example (single shared policy)."""

# All Sumo and network
from flow.envs.multiagent import MultiTrafficLightGridPOEnv
from flow.networks import TrafficLightGridNetwork
from flow.core.params import SumoParams, EnvParams, InitialConfig, NetParams
from flow.core.params import InFlows, SumoCarFollowingParams, VehicleParams
from flow.controllers import SimCarFollowingController, GridRouter, GridRandomRouter
# Ray registration and tune
from ray.tune.registry import register_env
from flow.utils.registry import make_create_env
#RLlib policy template
from ray.rllib.agents.ppo.ppo_policy import PPOTFPolicy
# MISC
import random
import os

# Experiment parameters
N_ROLLOUTS = 50  # number of rollouts per training iteration
N_CPUS = os.cpu_count() - 1  # number of parallel workers

# Environment parameters
WARMUP_STEPS = random.randint(0,100)
HORIZON = 600  # time horizon of a single rollout
TIME_STEP = 0.2 # time in seconds per step in the simulation
MAX_SPEED = 30 / 3.6  # enter speed for departing vehicles
INNER_LENGTH = 300  # length of inner edges in the traffic light grid network
LONG_LENGTH = 100  # length of final edge in route
SHORT_LENGTH = 300  # length of edges that vehicles start on
N_ROWS = 5  # number of row of bidirectional lanes
N_COLUMNS = 5  # number of columns of bidirectional lanes
N_LANES = 2 # number of lanes present in all edges
# number of vehicles originating in the left, right, top, and bottom edges
N_LEFT, N_RIGHT, N_TOP, N_BOTTOM = 1, 1, 1, 1
EDGE_INFLOW = 300  # inflow rate of vehicles at every edge

# SIMULATOR OPTIONS
RENDER = False
WARNINGS = False
EVALUATE = True

# we place a sufficient number of vehicles to ensure they confirm with the
# total number specified above. We also use a "right_of_way" speed mode to
# support traffic light compliance
vehicles = VehicleParams()
N_VEHICLES = (N_LEFT + N_RIGHT) * N_COLUMNS + (N_BOTTOM + N_TOP) * N_ROWS
vehicles.add(
    veh_id="human",
    acceleration_controller=(SimCarFollowingController, {}),
    car_following_params=SumoCarFollowingParams(
        min_gap=2.5,
        max_speed=MAX_SPEED,
        decel=7.5,  # avoid collisions at emergency stops
        speed_mode="right_of_way",
    ),
    routing_controller=(GridRandomRouter, {}),
    num_vehicles=N_VEHICLES)

# inflows of vehicles are place on all outer edges (listed here)
outer_edges = []
outer_edges += ["left{}_{}".format(N_ROWS, i) for i in range(N_COLUMNS)]
outer_edges += ["right0_{}".format(i) for i in range(N_ROWS)]
outer_edges += ["bot{}_0".format(i) for i in range(N_ROWS)]
outer_edges += ["top{}_{}".format(i, N_COLUMNS) for i in range(N_ROWS)]

# equal inflows for each edge (as dictate by the EDGE_INFLOW constant)
inflow = InFlows()
for edge in outer_edges:
    inflow.add(
        veh_type="human",
        edge=edge,
        vehs_per_hour=EDGE_INFLOW,
        depart_lane="free",
        depart_speed=MAX_SPEED)

flow_params = dict(
    # name of the experiment
    exp_tag="grid_0_{}x{}_i{}_multiagent".format(N_ROWS, N_COLUMNS, EDGE_INFLOW),

    # name of the flow environment the experiment is running on
    env_name=MultiTrafficLightGridPOEnv,

    # name of the network class the experiment is running on
    network=TrafficLightGridNetwork,

    # simulator that is used by the experiment
    simulator='traci',

    # sumo-related parameters (see flow.core.params.SumoParams)
    sim=SumoParams(
        restart_instance=True,
        sim_step=TIME_STEP,
        render=RENDER,
        print_warnings=WARNINGS,
    ),

    # environment related parameters (see flow.core.params.EnvParams)
    env=EnvParams(
        warmup_steps= WARMUP_STEPS,
        horizon=HORIZON,
        evaluate=EVALUATE,
        additional_params={
            "target_velocity": 50,
            "switch_time": 3,
            "num_observed": 2,
            "discrete": False,
            "tl_type": "actuated",
            "num_local_edges": 4,
            "num_local_lights": 4,
        },
    ),

    # network-related parameters (see flow.core.params.NetParams and the
    # network's documentation or ADDITIONAL_NET_PARAMS component)
    net=NetParams(
        inflows=inflow,
        additional_params={
            "speed_limit": MAX_SPEED + 5,  # inherited from grid0 benchmark
            "grid_array": {
                "short_length": SHORT_LENGTH,
                "inner_length": INNER_LENGTH,
                "long_length": LONG_LENGTH,
                "row_num": N_ROWS,
                "col_num": N_COLUMNS,
                "cars_left": N_LEFT,
                "cars_right": N_RIGHT,
                "cars_top": N_TOP,
                "cars_bot": N_BOTTOM,
            },
            "horizontal_lanes": N_LANES,
            "vertical_lanes": N_LANES,
        },
    ),

    # vehicles to be placed in the network at the start of a rollout (see
    # flow.core.params.VehicleParams)
    veh=vehicles,

    # parameters specifying the positioning of vehicles upon initialization
    # or reset (see flow.core.params.InitialConfig)
    initial=InitialConfig(
        spacing='custom',
        shuffle=True,
    ),
)

create_env, env_name = make_create_env(params=flow_params, version=0)

# Register as rllib env
register_env(env_name, create_env)

test_env = create_env()
obs_space = test_env.observation_space
act_space = test_env.action_space


def gen_policy():
    """Generate a policy in RLlib."""
    return PPOTFPolicy, obs_space, act_space, {}


# Setup PG with a single policy graph for all agents
POLICY_GRAPHS = {'tl': gen_policy()}


def policy_mapping_fn(_):
    """Map a policy in RLlib."""
    return 'tl'


POLICIES_TO_TRAIN = ['tl']
