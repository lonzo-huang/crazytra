use std::cell::UnsafeCell;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Lock-free SPSC ring buffer.
/// Capacity must be a power of two.
pub struct RingBuffer<T: Clone> {
    data:     Box<[UnsafeCell<Option<T>>]>,
    capacity: usize,
    mask:     usize,
    head:     AtomicUsize,
    tail:     AtomicUsize,
}

unsafe impl<T: Clone + Send> Send for RingBuffer<T> {}
unsafe impl<T: Clone + Send> Sync for RingBuffer<T> {}

impl<T: Clone> RingBuffer<T> {
    pub fn new(capacity: usize) -> Arc<Self> {
        assert!(capacity.is_power_of_two(), "Capacity must be power of 2");
        let data = (0..capacity)
            .map(|_| UnsafeCell::new(None))
            .collect::<Vec<_>>()
            .into_boxed_slice();
        Arc::new(Self {
            data,
            capacity,
            mask: capacity - 1,
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
        })
    }

    pub fn push(&self, item: T) -> Result<(), T> {
        let head      = self.head.load(Ordering::Relaxed);
        let next_head = (head + 1) & self.mask;
        if next_head == self.tail.load(Ordering::Acquire) {
            return Err(item);
        }
        unsafe { *self.data[head].get() = Some(item); }
        self.head.store(next_head, Ordering::Release);
        Ok(())
    }

    pub fn pop(&self) -> Option<T> {
        let tail = self.tail.load(Ordering::Relaxed);
        if tail == self.head.load(Ordering::Acquire) { return None; }
        let item = unsafe { (*self.data[tail].get()).take() };
        self.tail.store((tail + 1) & self.mask, Ordering::Release);
        item
    }

    pub fn len(&self) -> usize {
        let h = self.head.load(Ordering::Relaxed);
        let t = self.tail.load(Ordering::Relaxed);
        h.wrapping_sub(t) & self.mask
    }

    pub fn is_empty(&self) -> bool { self.len() == 0 }
    pub fn capacity(&self) -> usize { self.capacity }

    pub fn pop_batch(&self, buf: &mut Vec<T>, max: usize) -> usize {
        let mut count = 0;
        while count < max {
            match self.pop() {
                Some(item) => { buf.push(item); count += 1; }
                None => break,
            }
        }
        count
    }
}

pub struct RingProducer<T: Clone> { inner: Arc<RingBuffer<T>> }
pub struct RingConsumer<T: Clone> { inner: Arc<RingBuffer<T>> }

pub fn ring_channel<T: Clone>(capacity: usize) -> (RingProducer<T>, RingConsumer<T>) {
    let buf = RingBuffer::new(capacity);
    (RingProducer { inner: Arc::clone(&buf) }, RingConsumer { inner: buf })
}

impl<T: Clone> RingProducer<T> {
    /// Overwrite oldest on full — suitable for real-time market data.
    pub fn push_overwrite(&self, item: T) {
        if self.inner.push(item.clone()).is_err() {
            self.inner.pop();
            let _ = self.inner.push(item);
        }
    }
    pub fn len(&self) -> usize { self.inner.len() }
}

impl<T: Clone> RingConsumer<T> {
    pub fn pop(&self) -> Option<T> { self.inner.pop() }
    pub fn pop_batch(&self, buf: &mut Vec<T>, max: usize) -> usize {
        self.inner.pop_batch(buf, max)
    }
    pub fn is_empty(&self) -> bool { self.inner.is_empty() }
}
