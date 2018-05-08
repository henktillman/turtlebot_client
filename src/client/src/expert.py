#!/usr/bin/env python
import rospy
from geometry_msgs.msg import Twist
import tf
import numpy as np
import sys, os
import pdb
import time

##########################################################################################
# Importing trained expert from IRL package
##########################################################################################
IRL_ABS_PATH = "/home/cc/ee106b/sp18/class/ee106b-aax/ros_workspaces/IRL"
sys.path.append(os.path.abspath(IRL_ABS_PATH))

from algos import IntentionChoiceGAN
from envs import *
register_custom_envs()
import gym
env_fn = lambda: gym.make("Turtle-v0")
irl_dir = "/home/cc/ee106b/sp18/class/ee106b-aax/ros_workspaces/IRL/data/turtle"
irl_name = "intention_choice5"
n_intentions = 4
irl_model = IntentionChoiceGAN(irl_name, env_fn, n_intentions, None, None, None, checkpoint='{}/{}_model'.format(irl_dir, irl_name))

##########################################################################################
##########################################################################################

cmd_vel = rospy.Publisher('cmd_vel_mux/input/navi', Twist, queue_size=10)

# obstacle = True
# obstacle_center = vec(0, 1.2)
# obstacle_radius = 0.4

def get_pos(pos, rot):
    yaw = tf.transformations.euler_from_quaternion(rot)[2]
    return np.array([pos[0]/2, pos[1]/2, yaw])

def main():
    rospy.init_node('Turtlebot_Client', anonymous=False)

    rospy.loginfo("To stop TurtleBot CTRL + C")
    rospy.on_shutdown(shutdown)

    # setting up the transform listener to find turtlebot position
    listener = tf.TransformListener()
    from_frame = 'odom'
    to_frame = 'base_link'
    listener.waitForTransform(from_frame, to_frame, rospy.Time(), rospy.Duration(5.0))
    broadcaster = tf.TransformBroadcaster()

    # this is so that each loop of the while loop takes the same amount of time.  The controller works better 
    # if you have this here
    hertz = 10
    rate = rospy.Rate(hertz)

    # getting the position of the turtlebot
    start_pos, start_rot = listener.lookupTransform(from_frame, to_frame, listener.getLatestCommonTime(from_frame, to_frame))
    
    # 3x1 array, representing (x,y,theta) of robot starting state
    start_state = get_pos(start_pos, start_rot)

    t = 0
    # box = np.array([0.7, 0.4])
    box = np.array([0.735, 0.335])
    target = np.array([0.4, 0.7])
    box_angle = np.pi/8
    state = np.array([0,0,0])
    start_box_angle = np.arctan2(box[1] - state[1], box[0] - state[0])

    def _get_box_face_coords(box, box_angle, box_face_dist=0.30):
        angle = start_box_angle + np.pi + box_angle
        offset = box_face_dist * np.array([np.cos(angle), np.sin(angle)])
        return box + offset

    def _get_box_angle(state, box):
        return _get_angle(state, box)

    def _get_box_face_angle(state, box, box_angle):
        return _get_angle(state, _get_box_face_coords(box, box_angle))

    def _get_target_angle(state, target):
        return _get_angle(state, target)

    def _get_angle(state, other):
        angle = np.arctan2(other[1] - state[1], other[0] - state[0]) - state[2]
        while angle < -np.pi:
            angle += 2*np.pi
        while angle >= np.pi:
            angle -= 2*np.pi
        return angle

    def _get_obs(state, box, box_angle, target):
        return np.array([
            np.linalg.norm(state[:2] - _get_box_face_coords(box, box_angle)),
            _get_box_face_angle(state, box, box_angle),
            np.linalg.norm(state[:2] - box),
            _get_box_angle(state, box),
            np.linalg.norm(state[:2] - target),
            _get_target_angle(state, target)
        ])

    current_pos, current_rot = listener.lookupTransform(from_frame, to_frame, listener.getLatestCommonTime(from_frame, to_frame))
    # # 3x1 array, representing (x,y,theta) of current robot state
    current_state = get_pos(current_pos, current_rot)
    ob = _get_obs(current_state, box, box_angle, target)
    print(current_state, box, target)

    def get_ob_action(action):
        vel_msg = Twist()
        vel_msg.linear.x = 2*action[0]
        vel_msg.linear.y = 0
        vel_msg.linear.z = 0
        vel_msg.angular.x = 0 
        vel_msg.angular.y = 0
        vel_msg.angular.z = action[1]
        cmd_vel.publish(vel_msg)
        rate.sleep()
        current_pos, current_rot = listener.lookupTransform(from_frame, to_frame, listener.getLatestCommonTime(from_frame, to_frame))
        current_state = get_pos(current_pos, current_rot)
        ob = _get_obs(current_state, box, box_angle, target)
        return ob

    while ob[0] > 0.01:
        action = (np.clip(ob[0], 0.01, 0.1), np.clip(ob[1], -0.8, 0.8))
        ob = get_ob_action(action)
    while np.abs(ob[3]) > 0.05:
        action = (0, np.clip(ob[3], -0.8, 0.8))
        ob = get_ob_action(action)
    while ob[2] > 0.095:
        action = (np.clip(ob[2]-0.095, 0.01, 0.1), 0)
        ob = get_ob_action(action)
    while ob[4] > 0.095:
        action = (np.clip(ob[4]-0.095, 0.01, 0.1), np.clip(ob[5], -0.8, 0.8))
        ob = get_ob_action(action)

    # t = 0
    # while t < 193:
    #     # intention = irl_model.intention_policy.test_act([ob], irl_model.sess)[0]
    #     # one_hot_intention = np.zeros(n_intentions)
    #     # one_hot_intention[intention] = 1
    #     # action = irl_model.policy.test_act([np.concatenate((ob, one_hot_intention))], irl_model.sess)[0]
    #     intention_probs = irl_model.intention_policy.test_probs([ob], irl_model.sess)[0]
    #     action = np.zeros(2)
    #     for intention in range(n_intentions):
    #         one_hot_intention = np.zeros(n_intentions)
    #         one_hot_intention[intention] = 1
    #         action += intention_probs[intention] \
    #             * irl_model.policy.test_act([np.concatenate((ob, one_hot_intention))], irl_model.sess)[0]

    #     ob = get_ob_action(action)
    #     t += 1

    
def shutdown():
    rospy.loginfo("Stopping TurtleBot")
    cmd_vel.publish(Twist())
    rospy.sleep(1)
 
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print e
        rospy.loginfo("Turtlebot client node terminated.")
