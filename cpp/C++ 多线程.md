## C++ 多线程
C++ 多线程是指在一个程序中同时运行多个线程，每个线程都可以执行不同的代码段。
> 进程、线程相关概念可参考：[C++ 进程 线程](https://blog.csdn.net/Cloud_Manon/article/details/140547910)
### 多线程优点
1. **提高性能**：多线程可以提高程序的性能和响应速度。
2. **提高系统资源利用率**：多线程可以提高系统资源的利用率。
3. **提高程序的可靠性**：多线程可以提高程序的可靠性和容错性。
4. **提高程序的可扩展性**：多线程可以提高程序的可扩展性和可维护性。
5. **提高用户体验**：多线程可以提高用户体验，例如在 GUI 程序中，可以使用多线程来处理耗时的操作，而不阻塞主线程。
6. **提高吞吐量**：多线程可以提高程序的吞吐量，例如在服务器程序中，可以使用多线程来处理多个请求。
7. **提高资源利用率**：多线程可以提高资源利用率，例如在多核 CPU 中，可以使用多线程来利用多个核。
### 多线程缺点
1. **增加复杂性**：多线程会增加程序的复杂性，需要考虑线程同步、线程安全等问题。
2. **增加调试难度**：多线程会增加调试难度，需要使用特殊的调试工具和技术。
3. **增加内存使用**：多线程会增加内存使用，每个线程都需要自己的栈和寄存器。
4. **增加 CPU 使用**：多线程会增加 CPU 使用，每个线程都需要 CPU 时间片。
5. **增加死锁风险**：多线程会增加死锁风险，需要考虑线程同步和锁定机制。
6. **增加资源竞争**：多线程会增加资源竞争，需要考虑线程安全和资源保护机制。
7. **增加程序维护难度**：多线程会增加程序维护难度，需要考虑线程同步和锁定机制的维护。
## C++ 多线程同步机制
### 1. Mutexes (互斥量)
互斥量是一种常用的同步机制，用于保护对共享资源的访问，确保任何时候只有一个线程可以访问受保护的资源。
- `std::mutex`：基本的互斥量类型。
- `std::lock_guard`：一个RAII（Resource Acquisition Is Initialization）风格的类，用于自动锁定和解锁互斥量。
- `std::unique_lock`：与`std::lock_guard`类似，但提供了更多控制选项，例如尝试锁定和超时。

```cpp
#include <iostream>
#include <thread>
#include <mutex>

// 全局变量
int count = 0;

// 互斥锁
std::mutex mtx;

void thread_func() {
    // 加锁
    mtx.lock();
    // 临界区
    count++;
    std::cout << "Thread " << std::this_thread::get_id() << ": count = " << count << std::endl;
    // 解锁
    mtx.unlock();
}

int main() {
    // 创建 10 个线程
    std::thread threads[10];
    for (int i = 0; i < 10; i++) {
        threads[i] = std::thread(thread_func);
    }

    // 等待所有线程结束
    for (int i = 0; i < 10; i++) {
        threads[i].join();
    }

    return 0;
}

```
### 2. Condition Variables (条件变量)
条件变量通常与互斥量一起使用，用于在线程之间进行通信，允许一个线程等待直到满足特定条件，而另一个线程则通知条件满足。
- `std::condition_variable`：基础的条件变量类型。
- `std::condition_variable_any`：可以与任何类型的互斥量一起使用的条件变量。

```cpp
#include <iostream>
#include <thread>
#include <mutex>
#include <condition_variable>

// 全局变量
bool ready = false;

// 互斥锁
std::mutex mtx;
// 条件变量
std::condition_variable cv;

void thread_func() {
    // 加锁
    std::unique_lock<std::mutex> lock(mtx);
    // 等待信号
    cv.wait(lock, []{ return ready; });
    // 临界区
    std::cout << "Thread " << std::this_thread::get_id() << ": ready = " << ready << std::endl;
}

int main() {
    // 创建 10 个线程
    std::thread threads[10];
    for (int i = 0; i < 10; i++) {
        threads[i] = std::thread(thread_func);
    }

    // 等待 2 秒
    std::this_thread::sleep_for(std::chrono::seconds(2));

    // 加锁
    std::lock_guard<std::mutex> lock(mtx);
    // 设置 ready 为 true
    ready = true;
    // 发送信号
    cv.notify_all();

    // 等待所有线程结束
    for (int i = 0; i < 10; i++) {
        threads[i].join();
    }

    return 0;
}
```
### 3. Atomic Types (原子类型)
原子类型用于在不使用锁的情况下实现线程安全的操作，适用于简单的数据类型和操作。
`std::atomic<T>`：原子类型模板，支持各种原子操作。
- 优势
	- 让线程之间进行同步，从而避免线程之间的竞争和死锁。
	- 提高线程之间的通信效率，从而提高程序的性能。
	- 简化线程之间的同步代码，从而提高程序的可读性和可维护性。
- 常用操作
	- `fetch_add`：原子加法操作
	- `fetch_sub`：原子减法操作
	- `fetch_and`：原子与操作
	- `fetch_or`：原子或操作
	- `fetch_xor`：原子异或操作
	- `load`：原子加载操作
	- `store`：原子存储操作
	- `exchange`：原子交换操作
	- `compare_exchange`：原子比较交换操作

```cpp
#include <iostream>
#include <thread>
#include <atomic>

// 原子变量
std::atomic<int> count(0);

void thread_func() {
    // 原子操作
    count.fetch_add(1);
    std::cout << "Thread " << std::this_thread::get_id() << ": count = " << count << std::endl;
}

int main() {
    // 创建 10 个线程
    std::thread threads[10];
    for (int i = 0; i < 10; i++) {
        threads[i] = std::thread(thread_func);
    }

    // 等待所有线程结束
    for (int i = 0; i < 10; i++) {
        threads[i].join();
    }

    std::cout << "Final count: " << count << std::endl;

    return 0;
}
```
> C++ Atomic Types (原子类型) 主要用于**简单的变量类型**，例如 `int`, `bool`, `char` 等等。

> C++ Atomic Types (原子类型) **不建议使用在类上**：
> 1. **原子性仅限于单个变量**：当使用原子类型时，仅保证单个变量的原子性，而不保证整个类的原子性。如果类中有多个变量，使用原子类型并不能保证整个类的线程安全。
> 2. **类的拷贝和移动**：当类中包含原子类型的成员变量时，类的拷贝和移动操作可能会导致原子性丧失。因为拷贝和移动操作可能会涉及到多个变量的访问和修改，这可能会导致线程安全问题。
> 3. **类的构造和析构**：类的构造和析构函数可能会访问和修改类的成员变量，这可能会导致线程安全问题。如果类中包含原子类型的成员变量，构造和析构函数可能会破坏原子性。
> 4. **难以控制原子性**：当使用原子类型时，很难控制原子性的范围和粒度。因为原子类型仅保证单个变量的原子性，而不提供一种机制来控制整个类的原子性。

### C++ 多线程性能优化

C++ 多线程性能优化是一个复杂的话题，涉及到很多因素，包括**硬件、操作系统、编译器和程序设计**等。
这里是一些 C++ 多线程性能优化的技巧和建议：

1. 使用高效的线程库、并行算法：
    - **[Intel TBB](https://www.intel.cn/content/www/cn/zh/developer/tools/oneapi/onetbb.html)**：Intel TBB 是一个高效的线程库，提供了并行算法和数据结构。
    - **[Boost.Thread](https://www.boost.org/)**：Boost.Thread 是一个跨平台的线程库，提供了线程创建和管理的功能。
    
2. 减少线程之间的同步：
    - **使用锁**：锁可以保护共享资源，但也会引入性能开销。
    - **使用无锁数据结构**：无锁数据结构可以减少线程之间的同步。

4. 减少线程的创建和销毁，优化线程调度：
    - **使用线程池**：线程池可以减少线程创建和销毁的开销。
    
    	>  详细可参考：[C++ 线程池](https://blog.csdn.net/Cloud_Manon/article/details/139888096)
    
    - **使用任务队列**：任务队列可以优化线程调度。

		>  详细可参考：[C++ 任务队列](https://blog.csdn.net/Cloud_Manon/article/details/140790569)

	> **任务队列与线程池的区别**
	> | 特性 | 任务队列 | 线程池 |
	> | :--- | :--- | :--- |
	> | 主要功能 | 管理任务的执行顺序和优先级 | 提供可重用线程池来执行任务 |
	> | 任务执行方式 | 任务按顺序或优先级执行 | 任务由线程池中的线程执行 |
	> | 线程管理 | 不管理线程的创建和销毁 | 管理线程池中的线程的创建和销毁 |
	> | 线程数量 | 可以根据任务数量动态调整线程数量 | 线程数量固定或可配置 |
	> | 任务类型 | 支持多种任务类型（如异步任务、同步任务） | 支持多种任务类型（如异步任务、同步任务） |
	> | 任务调度 | 任务调度由任务队列管理 | 任务调度由线程池管理 |
	> | 线程阻塞 | 线程阻塞可能导致任务队列阻塞 | 线程阻塞不会导致任务队列阻塞 |
	> | 资源利用率 | 任务队列可能导致资源浪费（线程创建和销毁） | 线程池可以提高资源利用率（线程复用） |
	> | 复杂度 | 任务队列相对简单 | 线程池相对复杂 |
	> | 应用场景 | 管理任务的执行顺序和优先级<br>支持多种任务类型（如异步任务、同步任务）<br>动态调整线程数量 | 提高资源利用率（线程复用）<br>管理线程池中的线程的创建和销毁<br>支持高并发任务执行 |    

5. 减少线程之间的数据传输：
    - **使用共享内存**：共享内存可以减少线程之间的数据传输。
    - **使用消息队列**：消息队列可以优化线程之间的数据传输。

6. 优化线程的执行顺序：
    - **使用线程优先级**：线程优先级可以优化线程的执行顺序。
    - **使用线程调度算法**：线程调度算法可以优化线程的执行顺序。

8. 优化线程的资源使用：
    - **使用线程本地存储**：线程本地存储可以优化线程的资源使用。
    - **使用线程共享资源**：线程共享资源可以优化线程的资源使用。

> 常用 C++ 多线程性能优化工具：
> 1. **Intel VTune Amplifier**：Intel VTune Amplifier 是一个性能分析工具，可以帮助优化线程性能。
> 2. **Google Benchmark**：Google Benchmark 是一个性能测试框架，可以帮助评估线程性能。
> 3. **perf**：perf 是一个 Linux 性能分析工具，可以帮助优化线程性能。

> 常用 C++ 多线程性能优化库和框架：
> 1. **Intel TBB**：Intel TBB 是一个高效的线程库，提供了并行算法和数据结构。
> 2. **Boost.Thread**：Boost.Thread 是一个跨平台的线程库，提供了线程创建和管理的功能。
> 3. **OpenMP**：OpenMP 是一个并行编程模型，提供了并行算法和数据结构。
> 4. **std::thread**：std::thread 是 C++11 标准库中的线程库，提供了线程创建和管理的功能。
