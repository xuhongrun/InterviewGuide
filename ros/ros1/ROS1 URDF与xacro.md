# ROS1 URDF 与 xacro 建模

> URDF（Unified Robot Description Format）：用 XML 描述机器人**链接（link）+ 关节（joint）+ 几何 + 惯量**。xacro 在 URDF 之上提供宏 / 参数 / 包含。

---

## 一、URDF 基本骨架

```xml
<?xml version="1.0"?>
<robot name="my_robot">

  <link name="base_link">
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0"/>
      <geometry><box size="0.4 0.3 0.1"/></geometry>
      <material name="blue"><color rgba="0 0 1 1"/></material>
    </visual>
    <collision>
      <geometry><box size="0.4 0.3 0.1"/></geometry>
    </collision>
    <inertial>
      <mass value="2.0"/>
      <origin xyz="0 0 0"/>
      <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
    </inertial>
  </link>

  <link name="wheel_left"/>

  <joint name="wheel_left_joint" type="continuous">
    <parent link="base_link"/>
    <child link="wheel_left"/>
    <origin xyz="0 0.15 0" rpy="-1.5708 0 0"/>
    <axis xyz="0 0 1"/>
    <limit effort="10" velocity="5"/>
    <dynamics damping="0.1" friction="0.01"/>
  </joint>

</robot>
```

### Joint 类型

| type | 说明 |
|------|------|
| `fixed` | 完全固定（无自由度） |
| `revolute` | 旋转（有限位） |
| `continuous` | 旋转（无限位，如轮子） |
| `prismatic` | 平移（有限位） |
| `floating` | 6-DoF 自由 |
| `planar` | 平面 2D |

### 几何形状

`<box size="..."/>` / `<cylinder radius length/>` / `<sphere radius/>` / `<mesh filename="package://my_pkg/meshes/x.stl" scale="1 1 1"/>`。

---

## 二、惯量计算

```
长方体：
  ixx = 1/12 * m * (y² + z²)
  iyy = 1/12 * m * (x² + z²)
  izz = 1/12 * m * (x² + y²)

实心圆柱（沿 z）：
  ixx = iyy = 1/12 * m * (3 r² + h²)
  izz = 1/2  * m * r²

实心球：
  ixx = iyy = izz = 2/5 * m * r²
```

> ⚠️ **零惯量会导致 Gazebo 仿真发散**（NaN/爆炸），必须设置物理可行的惯量。

---

## 三、xacro：让 URDF 可维护

```xml
<?xml version="1.0"?>
<robot name="my_robot" xmlns:xacro="http://www.ros.org/wiki/xacro">

  <xacro:property name="wheel_radius" value="0.05"/>
  <xacro:property name="wheel_mass"   value="0.5"/>

  <xacro:macro name="wheel" params="prefix y_offset">
    <link name="${prefix}_wheel">
      <visual>
        <geometry><cylinder radius="${wheel_radius}" length="0.02"/></geometry>
      </visual>
      <inertial>
        <mass value="${wheel_mass}"/>
        <inertia ixx="${wheel_mass*wheel_radius*wheel_radius/4.0}" ixy="0" ixz="0"
                 iyy="${wheel_mass*wheel_radius*wheel_radius/4.0}" iyz="0"
                 izz="${wheel_mass*wheel_radius*wheel_radius/2.0}"/>
      </inertial>
    </link>
    <joint name="${prefix}_wheel_joint" type="continuous">
      <parent link="base_link"/>
      <child link="${prefix}_wheel"/>
      <origin xyz="0 ${y_offset} 0" rpy="-1.5708 0 0"/>
      <axis xyz="0 0 1"/>
    </joint>
  </xacro:macro>

  <xacro:wheel prefix="left"  y_offset=" 0.15"/>
  <xacro:wheel prefix="right" y_offset="-0.15"/>

  <xacro:include filename="$(find my_pkg)/urdf/sensors.xacro"/>
</robot>
```

### 编译

```bash
xacro robot.urdf.xacro > robot.urdf       # 离线渲染
# 或在 launch 内 inline
<param name="robot_description"
       command="$(find xacro)/xacro $(find my_pkg)/urdf/robot.urdf.xacro"/>
```

xacro 也支持 `<xacro:if>` / `<xacro:unless>` / `${math expression}` / `$(arg foo)`。

---

## 四、加载与可视化

`display.launch`：

```xml
<launch>
  <param name="robot_description"
         command="$(find xacro)/xacro $(find my_pkg)/urdf/robot.urdf.xacro"/>

  <node pkg="joint_state_publisher_gui" type="joint_state_publisher_gui"
        name="jsp_gui"/>
  <node pkg="robot_state_publisher" type="robot_state_publisher"
        name="rsp"/>

  <node pkg="rviz" type="rviz" name="rviz"
        args="-d $(find my_pkg)/rviz/view.rviz"/>
</launch>
```

- `joint_state_publisher_gui`：滑条手动驱动关节；
- `robot_state_publisher`：把 URDF + `/joint_states` 转成 TF 广播。

---

## 五、URDF + Gazebo

```xml
<gazebo reference="left_wheel">
  <mu1>1.0</mu1>
  <mu2>1.0</mu2>
  <kp>1e7</kp>
  <kd>1.0</kd>
  <material>Gazebo/Black</material>
</gazebo>

<gazebo>
  <plugin name="diff_drive" filename="libgazebo_ros_diff_drive.so">
    <leftJoint>left_wheel_joint</leftJoint>
    <rightJoint>right_wheel_joint</rightJoint>
    <wheelSeparation>0.30</wheelSeparation>
    <wheelDiameter>0.10</wheelDiameter>
    <commandTopic>cmd_vel</commandTopic>
    <odometryTopic>odom</odometryTopic>
    <odometryFrame>odom</odometryFrame>
    <robotBaseFrame>base_link</robotBaseFrame>
  </plugin>
</gazebo>
```

启动：

```bash
roslaunch gazebo_ros empty_world.launch
rosrun gazebo_ros spawn_model -urdf -param robot_description -model my_robot
```

---

## 六、检查与排错

```bash
check_urdf robot.urdf                    # 解析 + 树结构
urdf_to_graphiz robot.urdf               # 生成 PDF
rosrun xacro xacro --inorder file.xacro  # 编译 + 检查

rosrun tf view_frames                    # 检查 TF
rostopic echo /joint_states              # 检查关节状态
```

常见问题：

| 现象 | 排查 |
|------|------|
| RViz 中模型一闪而过 / 飞走 | 惯量为 0 / mesh 单位错误（mm vs m） |
| Gazebo 中机器人爆炸 | 惯量小于物理合理值，关节阻尼不足 |
| TF 缺 link → link | URDF 有但未启动 robot_state_publisher，或 link 没父关节 |
| 轮子方向不对 | `<axis>` 或 `<origin rpy>` 错；wheel 旋转轴一般是 z（在轮子 link 内） |

---

## 七、面试速记

- URDF = `<link> + <joint>`，必须含 `visual/collision/inertial`
- 惯量为 0 → Gazebo 物理发散
- xacro 提供宏 / 参数 / include；编译用 `xacro file > out.urdf`
- `robot_state_publisher` 把 URDF + `/joint_states` 转成 `/tf`
- Gazebo 用 `<gazebo>` 标签插入材质 / 插件
- mesh 单位用 m，scale 必要时调整
- 检查工具：`check_urdf` / `urdf_to_graphiz` / `view_frames`
