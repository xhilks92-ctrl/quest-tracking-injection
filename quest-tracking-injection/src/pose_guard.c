#define _GNU_SOURCE
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static volatile sig_atomic_t done;
static void stop(int sig) {
  (void)sig;
  done = 1;
}
static double now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec + t.tv_nsec * 1e-9;
}
int main(int argc, char **argv) {
  if (argc != 5) {
    fprintf(stderr, "PID LOAD_BIAS SECONDS HEAD_BUFFER (0 seconds restores)\n");
    return 2;
  }
  int pid = atoi(argv[1]);
  uint64_t base = strtoull(argv[2], 0, 0);
  double seconds = strtod(argv[3], 0);
  uint64_t head = strtoull(argv[4], 0, 0);
  if (pid < 1 || seconds < 0 || seconds > 60)
    return 2;
  char path[80];
  snprintf(path, sizeof(path), "/proc/%d/mem", pid);
  int fd = open(path, O_RDWR | O_CLOEXEC);
  if (fd < 0) {
    perror("open");
    return 1;
  }
  uint64_t sites[2] = {base + 0xaab4c, base + 0xa9830};
  uint32_t original = 0xd63f0100, nop = 0xd503201f, v;
  for (int j = 0; j < 2; j++)
    if (pread(fd, &v, 4, sites[j]) != 4 ||
        (seconds == 0 ? (v != nop && v != original) : v != original)) {
      fprintf(stderr, "Physical call instruction mismatch at %d\n", j);
      close(fd);
      return 1;
    }
  uint32_t last = 0, mode[4];
  if (seconds > 0 &&
      (!head || pread(fd, &last, 4, head + 0x14) != 4 ||
       pread(fd, mode, sizeof(mode), head + 0x15b0) != sizeof(mode) ||
       mode[0] != mode[1] || mode[2 + (mode[1] & 1)] != 0)) {
    fprintf(stderr,
            "Head tracking monitor unavailable or mode is not NORMAL\n");
    close(fd);
    return 1;
  }
  signal(SIGINT, stop);
  signal(SIGTERM, stop);
  signal(SIGHUP, stop);
  uint32_t wanted = seconds == 0 ? original : nop;
  int written = 0;
  for (int j = 0; j < 2; j++) {
    if (pwrite(fd, &wanted, 4, sites[j]) != 4) {
      perror("pwrite");
      if (seconds > 0)
        for (int k = 0; k < written; k++)
          pwrite(fd, &original, 4, sites[k]);
      close(fd);
      return 1;
    }
    written++;
  }
  printf("SOURCE_GUARD %s pid=%d guard_pid=%d seconds=%.1f\n",
         seconds == 0 ? "RESTORED" : "ACTIVE", pid, getpid(), seconds);
  fflush(stdout);
  int result = 0;
  if (seconds > 0) {
    double start = now();
    struct timespec delay = {0, 10000000};
    double progress = start;
    while (!done && now() - start < seconds) {
      uint32_t counter;
      if (pread(fd, &counter, 4, head + 0x14) != 4 ||
          pread(fd, mode, sizeof(mode), head + 0x15b0) != sizeof(mode)) {
        fprintf(stderr, "Head tracking monitor read failed\n");
        result = 1;
        break;
      }
      if (counter != last) {
        last = counter;
        progress = now();
      }
      if (now() - progress > 0.5 ||
          (mode[0] == mode[1] && mode[2 + (mode[1] & 1)] != 0)) {
        fprintf(stderr, "Head tracking stalled or left NORMAL mode; restoring "
                        "physical calls\n");
        result = 1;
        break;
      }
      nanosleep(&delay, 0);
    }
    for (int j = 0; j < 2; j++) {
      if (pread(fd, &v, 4, sites[j]) != 4 || v != nop) {
        fprintf(stderr, "Restore refused: unexpected instruction\n");
        result = 1;
      } else if (pwrite(fd, &original, 4, sites[j]) != 4) {
        perror("restore");
        result = 1;
      } else if (pread(fd, &v, 4, sites[j]) != 4 || v != original) {
        fprintf(stderr, "Restore verification failed\n");
        result = 1;
      }
    }
    printf("SOURCE_GUARD RESTORED result=%d\n", result);
  }
  close(fd);
  return result;
}
