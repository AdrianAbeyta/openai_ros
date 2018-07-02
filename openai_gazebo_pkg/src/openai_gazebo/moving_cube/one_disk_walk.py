import rospy
import numpy
import math
from gym import spaces
from openai_gazebo import cube_single_disk_env
from gym.envs.registration import register
from geometry_msgs.msg import Point

# The path is __init__.py of openai_gazebo, where we import the MovingCubeOneDiskWalkEnv directly
register(
        id='MovingCubeOneDiskWalk-v0',
        entry_point='openai_gazebo:MovingCubeOneDiskWalkEnv',
        timestep_limit=1000,
    )

class MovingCubeOneDiskWalkEnv(cube_single_disk_env.CubeSingleDiskEnv):
    def __init__(self):
        number_actions = rospy.get_param('/moving_cube/n_actions')
        self.action_space = spaces.Discrete(number_actions)
        # Variables that we retrieve through the param server, loded when launch training launch.
        self.roll_speed_fixed_value = rospy.get_param('/moving_cube/roll_speed_fixed_value')
        self.roll_speed_increment_value = rospy.get_param('/moving_cube/roll_speed_increment_value')

        self.max_distance = rospy.get_param('/moving_cube/max_distance')
        self.max_pitch_angle = rospy.get_param('/moving_cube/max_pitch_angle')
        self.max_yaw_angle = rospy.get_param('/moving_cube/max_yaw_angle')


        self.start_point = Point()
        self.start_point.x = rospy.get_param("/moving_cube/init_cube_pose/x")
        self.start_point.y = rospy.get_param("/moving_cube/init_cube_pose/y")
        self.start_point.z = rospy.get_param("/moving_cube/init_cube_pose/z")

        self.end_episode_points = rospy.get_param("/moving_cube/end_episode_points")

        self.init_roll_vel = rospy.get_param("/moving_cube/init_roll_vel")

        self.move_distance_reward_weight = rospy.get_param("/moving_cube/move_distance_reward_weight")
        self.y_linear_speed_reward_weight = rospy.get_param("/moving_cube/y_linear_speed_reward_weight")
        self.y_axis_angle_reward_weight = rospy.get_param("/moving_cube/y_axis_angle_reward_weight")


        # Here we will add any init functions prior to starting the CubeSingleDiskEnv
        super(MovingCubeOneDiskWalkEnv, self).__init__(self.init_roll_vel)

    def _init_env_variables(self):
        """
        Inits variables needed to be initialised each time we reset at the start
        of an episode.
        :return:
        """
        self.total_distance_moved = 0.0
        self.current_y_distance = self.get_y_dir_distance_from_start_point(self.start_point)
        self.roll_turn_speed = rospy.get_param('/moving_cube/init_roll_vel')


    def _set_action(self, action):

        # We convert the actions to speed movements to send to the parent class CubeSingleDiskEnv
        if action == 0:# Move Speed Wheel Forwards
            self.roll_turn_speed = self.roll_speed_fixed_value
        elif action == 1:# Move Speed Wheel Backwards
            self.roll_turn_speed = self.roll_speed_fixed_value
        elif action == 2:# Stop Speed Wheel
            self.roll_turn_speed = 0.0
        elif action == 3:# Increment Speed
            self.roll_turn_speed += self.roll_speed_increment_value
        elif action == 4:# Decrement Speed
            self.roll_turn_speed -= self.roll_speed_increment_value

        # We clamp Values to maximum
        rospy.logdebug("roll_turn_speed before clamp=="+str(self.roll_turn_speed))
        self.roll_turn_speed = numpy.clip(self.roll_turn_speed,
                                          -self.roll_speed_fixed_value,
                                          self.roll_speed_fixed_value)
        rospy.logdebug("roll_turn_speed after clamp==" + str(self.roll_turn_speed))

        # We tell the OneDiskCube to spin the RollDisk at the selected speed
        self.move_joints(self.roll_turn_speed)

    def _get_obs(self):
        """
        Here we define what sensor data defines our robots observations
        To know which Variables we have acces to, we need to read the
        CubeSingleDiskEnv API DOCS
        :return:
        """

        # We get the orientation of the cube in RPY
        roll, pitch, yaw = self.get_orientation_euler()

        # We get the distance from the origin
        #distance = self.get_distance_from_start_point(self.start_point)
        y_distance = self.get_y_dir_distance_from_start_point(self.start_point)

        # We get the current speed of the Roll Disk
        current_disk_roll_vel = self.get_roll_velocity()

        # We get the linear speed in the y axis
        y_linear_speed = self.get_y_linear_speed()

        cube_observations = [
            round(current_disk_roll_vel, 0),
            #round(distance, 1),
            round(y_distance, 1),
            round(roll, 1),
            round(pitch, 1),
            round(y_linear_speed,1),
            round(yaw, 1),
        ]

        return cube_observations

    def _is_done(self, observations):

        pitch_angle = observations[3]

        if abs(pitch_angle) > self.max_pitch_angle:
            rospy.logerr("WRONG Cube Pitch Orientation==>" + str(pitch_angle))
            done = True
        else:
            rospy.logdebug("Cube Pitch Orientation Ok==>" + str(pitch_angle))
            done = False

        return done

    def _compute_reward(self, observations, done):

        if not done:
            """
            distance_now = observations[1]
            delta_distance = distance_now - self.total_distance_moved
            # Reinforcement, pos if increase from the last time, negative if decrease
            reward_distance = delta_distance * self.move_distance_reward_weight
            self.total_distance_moved += delta_distance
            rospy.logdebug("Tot_dist=" + str(self.total_distance_moved))
            """
            y_distance_now = observations[1]
            delta_distance = y_distance_now - self.current_y_distance
            rospy.logdebug("y_distance_now=" + str(y_distance_now)+", current_y_distance=" + str(self.current_y_distance))
            rospy.logdebug("delta_distance=" + str(delta_distance))
            reward_distance = delta_distance * self.move_distance_reward_weight
            self.current_y_distance = y_distance_now

            y_linear_speed = observations[4]
            rospy.logdebug("y_linear_speed=" + str(y_linear_speed))
            reward_y_axis_speed = y_linear_speed * self.y_linear_speed_reward_weight

            # Negative Reward for yaw different from zero.
            yaw_angle = observations[5]
            rospy.logdebug("yaw_angle=" + str(yaw_angle))
            # Worst yaw is 90 and 270 degrees, best 0 and 180. We use sin function for giving reward.
            sin_yaw_angle = math.sin(yaw_angle)
            rospy.logdebug("sin_yaw_angle=" + str(sin_yaw_angle))
            reward_y_axis_angle = -1 * abs(sin_yaw_angle) * self.y_axis_angle_reward_weight


            # We are not intereseted in decimals of the reward, doesnt give any advatage.
            reward = round(reward_distance, 0) + round(reward_y_axis_speed, 0) + round(reward_y_axis_angle, 0)
            rospy.logdebug("reward_distance=" + str(reward_distance))
            rospy.logdebug("reward_y_axis_speed=" + str(reward_y_axis_speed))
            rospy.logdebug("reward_y_axis_angle=" + str(reward_y_axis_angle))
            rospy.logdebug("reward=" + str(reward))
        else:
            reward = -self.end_episode_points

        return reward

