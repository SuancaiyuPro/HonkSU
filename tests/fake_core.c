#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static volatile sig_atomic_t stopping = 0;
static void stop(int signal_number) { (void)signal_number; stopping = 1; }

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--version") == 0) {
        if (getenv("HONKSU_TEST_CORE_FAIL_VERSION")) return 4;
        puts("honk-core test fixture");
        return 0;
    }
    if (argc > 1 && strcmp(argv[1], "android-ebpf-probe") == 0) {
        if (argc > 2 && strcmp(argv[2], "--help") == 0) {
            puts("fixture --socket-identity");
            return 0;
        }
        const char *mode = getenv("HONKSU_TEST_PROBE");
        if (mode && strcmp(mode, "slow") == 0) sleep(5);
        if (mode && strcmp(mode, "fail") == 0) { puts("private-socket-identity: FAIL fixture"); return 7; }
        if (!mode || strcmp(mode, "incomplete") != 0) puts("private-socket-identity: OK (fixture)");
        puts("probe: OK (fixture)");
        return 0;
    }
    /* The managed test executor exposes host procfs with translated PIDs. */
    const char *mirror = getenv("HONKSU_TEST_PROC_ROOT");
    if (mirror) {
        char link_path[4096], target[128];
        long native_pid;
        FILE *self = fopen("/proc/self/stat", "r");
        if (!self || fscanf(self, "%ld", &native_pid) != 1) return 2;
        fclose(self);
        snprintf(link_path, sizeof(link_path), "%s/%ld", mirror, (long)getpid());
        snprintf(target, sizeof(target), "/proc/%ld", native_pid);
        unlink(link_path);
        if (symlink(target, link_path) != 0) return 3;
    }
    alarm(30);
    signal(SIGTERM, stop);
    signal(SIGINT, stop);
    puts("fixture ready");
    fflush(stdout);
    while (!stopping) pause();
    return 0;
}
