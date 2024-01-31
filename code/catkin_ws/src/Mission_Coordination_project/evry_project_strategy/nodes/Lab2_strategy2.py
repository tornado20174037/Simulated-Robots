#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist, Pose2D
from sensor_msgs.msg import Range
from nav_msgs.msg import Odometry
from tf.transformations import euler_from_quaternion

from evry_project_plugins.srv import DistanceToFlag
import math

class Robot:
    def __init__(self, robot_name):
        """Constructor of the class Robot
        The required publishers / subscribers are created.
        The attributes of the class are initialized

        Args:
            robot_name (str): Name of the robot, like robot_1, robot_2 etc. To be used for your subscriber and publisher with the robot itself
        """
        self.speed = 0.0
        self.angle = 0.0
        self.sonar = 0.0  # Sonar distance
        self.x, self.y = 0.0, 0.0  # coordinates of the robot
        self.yaw = 0.0  # yaw angle of the robot
        self.robot_name = robot_name

        '''Listener and publisher'''

        rospy.Subscriber(self.robot_name + "/sensor/sonar_front",
                         Range, self.callbackSonar)
        rospy.Subscriber(self.robot_name + "/odom",
                         Odometry, self.callbackPose)
        self.cmd_vel_pub = rospy.Publisher(
            self.robot_name + "/cmd_vel", Twist, queue_size=1)

    def callbackSonar(self, msg):
        """Callback function that gets the data coming from the ultrasonic sensor

        Args:
            msg (Range): Message that contains the distance separating the US sensor from a potential obstacle
        """
        self.sonar = msg.range

    def get_sonar(self):
        """Method that returns the distance separating the ultrasonic sensor from a potential obstacle
        """
        return self.sonar

    def callbackPose(self, msg):
        """Callback function that gets the data coming from the ultrasonic sensor

        Args:
            msg (Odometry): Message that contains the coordinates of the agent
        """
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        quaternion = msg.pose.pose.orientation
        quaternion_list = [quaternion.x,
                           quaternion.y, quaternion.z, quaternion.w]
        roll, pitch, yaw = euler_from_quaternion(quaternion_list)
        self.yaw = yaw

    def get_robot_pose(self):
        """Method that returns the position and orientation of the robot"""
        return self.x, self.y, self.yaw

    def constraint(self, val, min=-2.0, max=2.0):
        """Method that limits the linear and angular velocities sent to the robot

        Args:
            val (float): [Desired velocity to send
            min (float, optional): Minimum velocity accepted. Defaults to -2.0.
            max (float, optional): Maximum velocity accepted. Defaults to 2.0.

        Returns:
            float: Limited velocity whose value is within the range [min; max]
        """
        # DO NOT TOUCH
        if val < min:
            return min
        if val > max:
            return max
        return val

    def set_speed_angle(self, linear, angular):
        """Method that publishes the proper linear and angular velocities commands on the related topic to move the robot

        Args:
            linear (float): desired linear velocity
            angular (float): desired angular velocity
        """
        cmd_vel = Twist()
        cmd_vel.linear.x = self.constraint(linear)
        cmd_vel.angular.z = self.constraint(angular, min=-1, max=1)
        self.cmd_vel_pub.publish(cmd_vel)

    def getDistanceToFlag(self):
        """Get the distance separating the agent from a flag. The service 'distanceToFlag' is called for this purpose.
        The current position of the robot and its id should be specified. The id of the robot corresponds to the id of the flag it should reach


        Returns:
            float: the distance separating the robot from the flag
        """
        rospy.wait_for_service('/distanceToFlag')
        try:
            service = rospy.ServiceProxy('/distanceToFlag', DistanceToFlag)
            pose = Pose2D()
            pose.x = self.x
            pose.y = self.y
            # int(robot_name[-1]) corresponds to the id of the robot. It is also the id of the related flag
            result = service(pose, int(self.robot_name[-1]))
            return result.distance
        except rospy.ServiceException as e:
            print("Service call failed: %s" % e)
    def calculate_pid(self, error, integral, derivative, kp, ki, kd):

        return kp * error + ki * integral + kd * derivative
    def obstacle_avoidance(self, min_safe_distance=3):
        """ Simple obstacle avoidance strategy """
        sonar_distance = float(self.get_sonar())
        print("Sonar distance:", sonar_distance)
        print("min distance:", min_safe_distance)
        if sonar_distance <= min_safe_distance:
            return True  # Obstacle detected
        return False # No obstacle detected

def run_demo():
    """Main loop"""
    robot_name = rospy.get_param("~robot_name")
    robot = Robot(robot_name)
    robot_id = int(robot_name.split('_')[-1])  # Extracting the numeric ID
    start_delay = robot_id * 3  # Delay in seconds
    rospy.sleep(start_delay)  # Wait for the delay
    
    
    print(f"Robot : {robot_name} is starting..")

    # Timing

    while not rospy.is_shutdown():
        # Strategy
        velocity = 1
        angle = 0
        distance = float(robot.getDistanceToFlag())
        threshold = 3 #the minimum distance for safety
        integral = 0
        last_error = 0
        kp = 0.5 # Proportional constant
        ki = 0.01  # Integral constant
        kd = 0.05  # Derivative constant
        

        print(f"{robot_name} distance to flag = ", distance)

        # Write here your strategy..
       
        #avoidance_angle = 45 # Angle changed for avoiding obstacles
        
        error = distance - threshold
        initial_direction = angle # 初始方向
        avoidance_angle = math.radians(45)  # The turning angle for obstacle avoidance
        turn_rate = math.radians(5)  # Angle adjustment rate for each iteration
        # PID calculations
        integral += error
        derivative = error - last_error
        output = robot.calculate_pid(error, integral, derivative, kp, ki, kd)
        last_error = error

        # Adjust linear velocity based on PID output
        if distance - threshold > 0.01:
           velocity = max(min(output, 2.0), 0) # Limit velocity to a safe range
        else :
            velocity = 0
        
        print("{robot_name} vitesse: %f" % velocity)

        # Adjust angular velocity to face towards the flag
        # This is a simplistic approach and may need more sophisticated handling
        #angle_to_flag = math.atan2(flag.pose.x - robot.y, flag_x - robot.x)
        # angular_velocity = angle_to_flag - robot.yaw

        if robot.obstacle_avoidance():
            robot.set_speed_angle(0, 0)
            rospy.sleep(1)
             # Obstacles detected, stop and change direction
            robot.set_speed_angle(0, avoidance_angle)
            rospy.sleep(1)
            # Start moving forward and gradually adjust the direction
            target_direction = (initial_direction + avoidance_angle) % (2 * math.pi)
            while initial_direction <= target_direction :
                # Adjust the robot's direction smoothly
                robot.set_speed_angle(1, -2*turn_rate )
                target_direction -= turn_rate
                rospy.sleep(0.5)
            robot.set_speed_angle(0.5, -turn_rate)  #Slightly adjust the direction to eliminate the error
            rospy.sleep(0.5)

            robot.set_speed_angle(1, 0)# Keep moving with this direction
        # Finishing by publishing the desired speed. 
        # DO NOT TOUCH.
        robot.set_speed_angle(velocity, angle)
        rospy.sleep(0.5)


if __name__ == "__main__":
    print("Running ROS..")
    rospy.init_node("Controller", anonymous=True)
    run_demo()
