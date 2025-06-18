## C++ 进程（Processes）
在 C++ 中，进程是指一个**独立的执行单元**，它拥有自己的内存空间、寄存器、程序计数器等资源。每个进程都运行在自己的地址空间中，互不干扰。
### 进程创建和管理
#### 进程创建
1. **fork 函数**：创建一个新的进程，返回两次：一次在父进程中，返回子进程的进程 ID；一次在子进程中，返回 0。
2. **vfork 函数**：创建一个新的进程，类似于 fork，但不拷贝父进程的内存空间。
3. **clone 函数**：创建一个新的进程，类似于 fork，但可以指定新的进程的内存空间和寄存器。
#### 进程管理
1. **wait 函数**：等待子进程结束，获取其退出状态。
2. **waitpid 函数**：等待指定的子进程结束，获取其退出状态。
3. **kill 函数**：向进程发送信号，以终止或中断进程。
4. **signal 函数**：设置信号处理函数，以捕捉和处理信号。
### 进程状态
- **running**：进程正在执行。
- **sleeping**：进程正在等待某个事件的发生。
- **zombie**：进程已经终止，但其父进程还没有等待其结束。
- **orphan**：进程的父进程已经终止，但该进程还没有终止。
### 进程间通信（Inter-Process Communication，IPC）
进程间通信（Inter-Process Communication，IPC）是指不同进程之间的数据交换和同步。常见的 IPC 方式有：
1. **管道（Pipe）**：使用管道可以在父进程和子进程之间传递数据。
使用 pipe 函数创建一个匿名管道，使用 mkfifo 函数创建一个命名管道。
2. **共享内存（Shared Memory）**：使用共享内存可以在多个进程之间共享数据。
使用 shm_open 函数创建一个共享内存区域，使用 shmget 函数获取一个共享内存区域的标识符。
3. **消息队列（Message Queue）**：使用消息队列可以在多个进程之间传递消息。
使用 msgget 函数创建一个消息队列，使用 msgsnd 函数向消息队列发送消息，使用 msgrcv 函数从消息队列接收消息。
4. **套接字（Socket）**：使用套接字可以在不同进程之间或不同机器之间传递数据。
使用 socket 函数创建一个套接字，使用 connect 函数连接到一个套接字，使用 send 函数向套接字发送数据，使用 recv 函数从套接字接收数据。
### 进程同步（Process Synchronization）
1. 互斥锁（Mutex）：使用互斥锁可以锁定一个资源，以避免多个进程同时访问该资源。
使用 `pthread_mutex_init` 函数初始化一个互斥锁，使用 `pthread_mutex_lock` 函数锁定一个互斥锁，使用 `pthread_mutex_unlock` 函数解锁一个互斥锁。
2. 条件变量（Condition Variable）：使用条件变量可以等待一个条件的满足，以避免busy waiting。
使用 `pthread_cond_init` 函数初始化一个条件变量，使用 `pthread_cond_wait` 函数等待一个条件变量，使用 `pthread_cond_signal` 函数唤醒一个条件变量。
3. 信号量（Semaphore）：使用信号量可以控制多个进程对一个资源的访问，以避免过度访问。
使用 `sem_init` 函数初始化一个信号量，使用 `sem_wait` 函数等待一个信号量，使用 `sem_post` 函数释放一个信号量。
> 进程相关的系统调用
> - getpid 函数：获取当前进程的进程 ID。
> - getppid 函数：获取当前进程的父进程 ID。
> - getuid 函数：获取当前进程的用户 ID。
> - getgid 函数：获取当前进程的组 ID。
## C++ 线程（Threads）
C++中的线程（Thread）是一种轻量级的进程，是一个程序中的最小执行单元。它可以并发执行多个任务，提高程序的响应速度和效率。**每个线程都有自己的栈空间，并共享相同的全局变量和堆空间。**
C++11标准中引入了std::thread类，提供了创建和管理线程的功能。
### 线程创建和管理
#### std::thread
std::thread 是 C++ 标准库中的一**类**，表示单个线程的执行。它提供了一种创建、管理和与线程交互的方式。
1. std::thread 的定义
```cpp
namespace std {
    class thread {
    public:
        // 默认构造函数
        thread() noexcept;

        // 构造函数
        template <class F, class... Args>
        explicit thread(F&& f, Args&&... args);

        // 构造函数 (copy constructor)
        thread(const thread&) = delete;

        // 构造函数 (move constructor)
        thread(thread&&) noexcept;

        // 析构函数
        ~thread();

        // operator=
        thread& operator=(const thread&) = delete;

        // operator=
        thread& operator=(thread&&) noexcept;

        // 获取线程 ID
        id get_id() const noexcept;

        // 获取线程状态
        state state() const noexcept;

        // 加入线程
        void join();

        // 分离线程
        void detach();

        // 获取线程的 native_handle
        native_handle_type native_handle();

        // 交换线程
        void swap(thread& other) noexcept;

        // 等待线程完成
        void wait();

        // 确定线程是否joinable
        bool joinable() const noexcept;

        // 确定线程是否已经启动
        bool started() const noexcept;

        // 确定线程是否已经完成
        bool finished() const noexcept;

    private:
        // 实现-defined
        void _M_start_thread(_Fn&& _Fn, _Args&&... _Args);
        void _M_join();
        void _M_detach();
        void _M_swap(thread& __other);

        // 数据成员
        _Impl _M_impl;
    };
}

```
2. 常用API
	- `std::thread()`
		默认构造函数，创建一个空线程对象。
	- `std::thread(F&& f, Args&&... args)`
		构造函数，创建一个线程对象并执行可调用对象 f。
	- `std::thread::id get_id() const noexcept`
		获取线程的唯一标识符。
	- `void join()`
		加入线程，阻塞调用线程直到线程完成执行。
	- `void detach()`
		分离线程，使线程独立于 std::thread 对象运行。
	- `std::thread::state state() const noexcept`
		获取线程的状态，可以是 running、joinable 或 detached。
		> **running**：线程正在执行。
		> **joinable**：线程可以被加入。
		> **detached**：线程已经被分离。
	- `void swap(std::thread& other) noexcept`
		交换两个线程对象的状态。
	- `void wait()`
		等待线程完成执行。
	- `bool joinable() const noexcept`
		确定线程是否可以被加入。
	- `bool started() const noexcept`
		确定线程是否已经启动。
	- `bool finished() const noexcept`
		确定线程是否已经完成。
	- `native_handle_type native_handle()`
		获取线程的 native_handle。
3. std::thread 的注意点
**线程安全**：std::thread 对象**不是线程安全的**，从多个线程访问同一个 std::thread 对象可能会导致未定义的行为。
**线程本地存储**：每个线程都有其自己的线程本地存储，可以用于存储特定于该线程的数据。
**同步**：std::thread 不提供内置的同步机制；开发者必须使用其他同步原语（例如互斥锁、条件变量）来协调线程执行。
4. 示例
```cpp
std::thread t1([]{ std::cout << "Hello, world!" << std::endl; }); // 创建一个线程对象
std::thread t2 = std::move(t1); // 移动线程对象

t2.join(); // 加入线程

std::thread t3;
t3.detach(); // 分离线程

std::thread t4([]{ std::cout << "Hello, world!" << std::endl; });
std::thread::id tid = t4.get_id(); // 获取线程 ID

std::thread t5;
std::thread t6 = std::move(t5);
t6.swap(t5); // 交换线程对象

std::thread t7([]{ std::cout << "Hello, world!" << std::endl; });
t7.wait(); // 等待线程完成

std::thread t8;
if (t8.joinable()) { // 确定线程是否可以被加入
    t8.join();
}

std::thread t9;
if (t9.started()) { // 确定线程是否已经启动
    std::cout << "Thread started!" << std::endl;
}

std::thread t10;
if (t10.finished()) { // 确定线程是否已经完成
    std::cout << "Thread finished!" << std::endl;
}
```
#### std::async
std::async 是 C++11 中引入的一个**函数**，它允许开发者异步执行一个函数，即在一个独立的线程中执行该函数。异步执行可以提高程序的性能和响应速度。
1. std::async 的定义
```cpp
std::future<T> std::async(std::launch policy, F&& f, Args&&... args);
```
- T 是函数 f 的返回类型。
- policy 是启动策略，可以是 std::launch::async 或 std::launch::deferred。
- F 是函数 f 的类型。
- f 是要异步执行的函数。
- args 是要传递给 f 的参数。
> 1. **启动策略**：std::launch::async 表示函数将在新的线程中**异步执行**，而 std::launch::deferred 表示函数将在等待 std::future 对象时**同步执行**。
> 2. **异步执行**：std::async 会将函数异步执行在一个独立的线程中，这可以提高程序的性能和响应速度。
> 3. **std::future**：std::async 返回一个 std::future 对象，该对象可以用于检索异步操作的结果。
> 4. **异常处理**：如果在异步函数执行期间抛出异常，它将被存储在 std::future 对象中，并**在调用 get() 时重新抛出**。
2. 常用API
	- `std::future<T> std::async(std::launch policy, F&& f, Args&&... args);`
		异步执行函数 f，并返回一个 std::future 对象，该对象可以用于检索异步操作的结果。
	- `std::future<T> f;`
		std::future 对象用于检索异步操作的结果。
	- `T std::future::get();`
		阻塞直到异步操作完成，并返回结果。
	- `void std::future::wait();`
		阻塞直到异步操作完成。
	- `std::future_status std::future::wait_for(std::chrono::duration dur);`
		阻塞直到异步操作完成或指定的持续时间已过期。
	- `std::future_status std::future::wait_until(std::chrono::time_point tp);`
		阻塞直到异步操作完成或指定的时间点已到达。
	- `std::launch policy;`
		指定 std::async 的启动策略，可以是 std::launch::async 或 std::launch::deferred。
3. std::async 的注意点
**线程安全**：std::async 会在新的线程中执行函数，因此需要确保函数是线程安全的。
**资源管理**：需要确保异步函数执行完成后释放资源，以免出现资源泄露。
**异常处理**：需要正确处理异步函数执行期间抛出的异常。
4. 示例
- 在这个示例中，使用 std::async 异步执行 add 函数，并将结果存储在 std::future 对象中。使用 get() 函数检索异步操作的结果。
```cpp
#include <iostream>
#include <future>

int add(int a, int b) {
    return a + b;
}

int main() {
    std::future<int> result = std::async(std::launch::async, add, 2, 3);
    std::cout << "Result: " << result.get() << std::endl;
    return 0;
}
```

- 在这个示例中，使用 std::async 异步执行 asyncFunc 函数，并使用 **wait()** 函数**等待异步函数执行完成**。
```cpp
#include <iostream>
#include <future>

void asyncFunc() {
    std::cout << "Async function executed." << std::endl;
}

int main() {
    std::future<void> result = std::async(std::launch::async, asyncFunc);
    result.wait(); // 等待异步函数执行完成
    return 0;
}
```

- 在这个示例中，使用 std::async 异步执行 asyncFunc 函数，该函数抛出一个异常。使用 get() 函数检索异步操作的结果。
```cpp
#include <iostream>
#include <future>

int asyncFunc() {
    throw std::runtime_error("Async function threw an exception.");
}

int main() {
    std::future<int> result = std::async(std::launch::async, asyncFunc);
    try {
        result.get(); // 检索异步操作的结果
    } catch (const std::exception& e) {
        std::cerr << "Exception caught: " << e.what() << std::endl;
    }
    return 0;
}
```
#### std::thread、std::async 区别
| | std::thread | std::async |
| --- | --- | --- |
| 线程管理 | 需要明确地管理线程的生命周期 | 自动管理线程创建和同步 |
| 同步 | 需要使用同步原语（例如互斥锁、条件变量） | 提供 std::future 对象，自动同步 |
| 结果检索 | 不提供内置的方式来检索结果 | 返回 std::future 对象，检索结果 |
| 线程创建 | 需要明确地创建线程 | 自动创建线程 |
| 线程生命周期 | 需要明确地管理线程的生命周期 | 自动管理线程的生命周期 |
| 使用场景 | 需要细粒度控制线程创建和管理 | 需要创建异步任务，检索结果 |
| 抽象级别 | 低级别，需要手动管理线程 | 高级别，自动管理线程 |
#### std::thread、std::async 使用场景
##### std::thread
- **长时间任务**：当您需要执行长时间任务时，不阻塞主线程，例如：数据处理、网络操作、 数据库查询
- **后台任务**：当您需要在后台执行任务时，例如：索引数据、发送通知、更新 UI 组件
- **并发编程**：当您需要执行并发编程时，例如：并行算法、实现并发数据结构、创建并发管道
- **系统编程**：当您需要执行系统级编程时，例如：创建系统服务、实现设备驱动、管理系统资源
##### std::async
- **异步操作**：当您需要执行异步操作时，例如：调用 API、发送请求到服务器、执行 I/O 操作
- **任务基于编程**：当您需要执行任务基于编程时，例如：创建任务队列、实现任务依赖、管理任务资源
- **GUI 编程**：当您需要执行 GUI 编程时，例如：更新 UI 组件、处理用户输入、创建动画
- **实时系统**：当您需要执行实时系统编程时，例如：实现实时算法、创建实时数据处理管道、管理实时系统资源

总的来说，std::thread 用于执行**长时间任务，不阻塞主线程**，而 std::async 用于执行**异步操作，返回结果**。
### 线程间通信（Inter-Thread Communication）
线程间通信是指多个线程之间交换数据和协调工作的机制。由于线程之间共享同一个进程的虚拟地址空间，因此可以使用共享变量、互斥锁、条件变量等机制来实现线程间通信。
1. **共享变量（Shared Variables）**：多个线程可以访问同一个共享变量，以交换数据。
2. **互斥锁（Mutex）**：使用互斥锁来保护共享变量，以避免数据竞争。
3. **条件变量（Condition Variable）**：使用条件变量来实现线程之间的同步和通信。
4. **信号量（Semaphore）**：使用信号量来控制线程之间的访问顺序。
5. **消息队列（Message Queue）**：使用消息队列来实现线程之间的异步通信。
### 线程同步（Thread Synchronization）
线程同步是指多个线程之间的协调和协作，以**避免数据竞争和死锁**。由于线程之间共享同一个进程的虚拟地址空间，因此需要使用同步机制来保护共享资源。
1. **互斥锁（Mutex）**：使用互斥锁来保护共享资源，以避免数据竞争。
2. **条件变量（Condition Variable）**：使用条件变量来实现线程之间的同步和通信。
3. **信号量（Semaphore）**：使用信号量来控制线程之间的访问顺序。
4. **读写锁（Read-Write Lock）**：使用读写锁来保护共享资源，以避免数据竞争。
5. **原子操作（Atomic Operation）**：使用原子操作来实现线程安全的数据访问。
## C++ 进程、线程的区别
| 特性 | 进程（Process） | 线程（Thread） |
| --- | --- | --- |
| 地址空间 | 独立的虚拟地址空间 | 共享同一个进程的虚拟地址空间 |
| 资源 | 拥有自己的资源，如打开的文件描述符、信号处理程序等 | 共享同一个进程的资源 |
| 通信 | 需要使用特殊的机制，如管道、套接字、共享内存等 | 可以通过共享变量、互斥锁、条件变量等机制实现 |
| 创建和销毁 | 需要操作系统的支持 | 可以由程序员控制 |
| 切换成本 | 高 | 低 | | 执行单元 | 独立的执行单元 | 轻量级的执行单元 |
| 同步 | 需要使用特殊的机制，如信号量、互斥锁等 | 可以使用标准库中的同步机制，如 std::mutex、std::condition_variable 等 |
| 数据共享 | 不能直接共享数据 | 可以直接共享数据 |
| 上下文切换 | 需要操作系统的支持 | 可以由程序员控制 |
| 优点 | 提高系统的并发性和吞吐量 | 提高系统的并发性和响应速度 |
| 缺点 | 创建和销毁的成本高 | 需要注意同步和数据共享的问题 |
