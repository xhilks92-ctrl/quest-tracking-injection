/* Quest 1, firmware 49845030443200410. Native, bounded Binder pose injector. */
#include <android/binder_ibinder.h>
#include <android/binder_parcel.h>
#include <android/binder_status.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopped;
static unsigned rejected_calls;
static unsigned streamed_poses, invalid_lines;
static void stream_pose(float *pos, float *rot) {
    static char pending[8192];
    static size_t used;
    ssize_t n = read(STDIN_FILENO, pending + used, sizeof(pending) - 1 - used);
    if (n <= 0)
        return;
    used += (size_t)n;
    pending[used] = 0;
    char *start = pending, *line;
    while ((line = strchr(start, '\n'))) {
        *line = 0;
        float v[7] = {0};
        char extra;
        int count = sscanf(start, "%f %f %f %f %f %f %f %c", v, v + 1, v + 2, v + 3, v + 4, v + 5,
                           v + 6, &extra);
        int valid = count == 7;
        double norm = 0;
        for (int j = 0; j < 7 && valid; j++)
            if (!isfinite(v[j]))
                valid = 0;
        for (int j = 3; j < 7; j++)
            norm += (double)v[j] * v[j];
        if (!isfinite(norm) || norm < 1e-12)
            valid = 0;
        if (valid) {
            memcpy(pos, v, 3 * sizeof(float));
            norm = sqrt(norm);
            for (int j = 0; j < 4; j++)
                rot[j] = (float)(v[j + 3] / norm);
            streamed_poses++;
        } else
            invalid_lines++;
        start = line + 1;
    }
    size_t remain = used - (size_t)(start - pending);
    memmove(pending, start, remain);
    used = remain;
    if (used == sizeof(pending) - 1) {
        used = 0;
        invalid_lines++;
    }
}
static void stop(int sig) {
    (void)sig;
    stopped = 1;
}
static void *create(void *p) { return p; }
static void destroy(void *p) { (void)p; }
static binder_status_t unused(AIBinder *b, transaction_code_t c, const AParcel *i, AParcel *o) {
    (void)b;
    (void)c;
    (void)i;
    (void)o;
    return STATUS_UNKNOWN_TRANSACTION;
}
static int transact(AIBinder *b, int code, const char *id, int field, const float *values,
                    int length) {
    AParcel *in = NULL, *out = NULL;
    AStatus *status = NULL;
    bool accepted = false;
    binder_status_t rc = AIBinder_prepareTransaction(b, &in);
    if (rc == STATUS_OK && code == 1)
        rc = AParcel_writeString(in, id, (int)strlen(id));
    if (rc == STATUS_OK)
        rc = AParcel_writeInt32(in, field);
    if (rc == STATUS_OK && code == 1)
        rc = AParcel_writeFloatArray(in, values, length);
    if (rc == STATUS_OK)
        rc = AIBinder_transact(b, code, &in, &out, 0);
    if (rc == STATUS_OK)
        rc = AParcel_readStatusHeader(out, &status);
    if (rc == STATUS_OK && !AStatus_isOk(status)) {
        fprintf(stderr, "Binder exception: %d %s\n", AStatus_getExceptionCode(status),
                AStatus_getMessage(status));
        rc = STATUS_FAILED_TRANSACTION;
    }
    if (rc == STATUS_OK)
        rc = AParcel_readBool(out, &accepted);
    if (in)
        AParcel_delete(in);
    if (out)
        AParcel_delete(out);
    if (status)
        AStatus_delete(status);
    if (rc != STATUS_OK || !accepted)
        fprintf(stderr, "Transaction %d field/mode %d: transport=%d accepted=%d\n", code, field, rc,
                accepted);
    return rc != STATUS_OK ? -1 : accepted ? 1 : 0;
}
static int pose(AIBinder *b, const char *id, int field, const float *v, int n) {
    for (int attempt = 0; attempt < 3 && !stopped; attempt++) {
        int r = transact(b, 1, id, field, v, n);
        if (r == 1)
            return 1;
        if (r < 0)
            return 0;
        rejected_calls++;
        struct timespec pause = {0, 1000000};
        nanosleep(&pause, NULL);
    }
    return 0;
}
static double number(const char *s) {
    char *end;
    errno = 0;
    double v = strtod(s, &end);
    if (errno || end == s || *end || !isfinite(v)) {
        fprintf(stderr, "Invalid number: %s\n", s);
        exit(2);
    }
    return v;
}
int main(int argc, char **argv) {
    if (argc != 12 && !(argc == 13 && !strcmp(argv[12], "--stdin"))) {
        fprintf(stderr, "Usage: quest-inject DEVICE_ID X Y Z QX QY QZ QW SECONDS HZ RESTORE_MODE "
                        "[--stdin]\nUse the accompanying Python launcher to determine RESTORE_MODE "
                        "automatically.\n");
        return 2;
    }
    char *end;
    errno = 0;
    strtoull(argv[1], &end, 0);
    if (errno || end == argv[1] || *end || argv[1][0] == '-')
        return 2;
    float pos[3], rot[4];
    for (int j = 0; j < 3; j++)
        pos[j] = (float)number(argv[2 + j]);
    for (int j = 0; j < 4; j++)
        rot[j] = (float)number(argv[5 + j]);
    double duration = number(argv[9]), hz = number(argv[10]), restore_value = number(argv[11]);
    if (duration <= 0 || duration > 60 || hz < 1 || hz > 500 ||
        (restore_value != 0 && restore_value != 1))
        return 2;
    for (int j = 0; j < 3; j++)
        if (!isfinite(pos[j]))
            return 2;
    double norm = 0;
    for (int j = 0; j < 4; j++)
        norm += (double)rot[j] * rot[j];
    if (!isfinite(norm) || norm < 1e-12)
        return 2;
    norm = sqrt(norm);
    for (int j = 0; j < 4; j++)
        rot[j] = (float)(rot[j] / norm);
    int streaming = argc == 13;
    if (streaming) {
        int flags = fcntl(STDIN_FILENO, F_GETFL);
        if (flags < 0 || fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0)
            return 1;
    }
    signal(SIGINT, stop);
    signal(SIGTERM, stop);
    signal(SIGHUP, stop);
    void *lib = dlopen("libbinder_ndk.so", RTLD_NOW);
    if (!lib) {
        fprintf(stderr, "%s\n", dlerror());
        return 1;
    }
    AIBinder *(*check)(const char *) =
        (AIBinder * (*)(const char *)) dlsym(lib, "AServiceManager_checkService");
    if (!check) {
        fprintf(stderr, "Service manager entry missing\n");
        return 1;
    }
    AIBinder *b = check("TrackingDataInjection");
    if (!b) {
        fprintf(stderr, "TrackingDataInjection unavailable\n");
        return 1;
    }
    AIBinder_Class *c = AIBinder_Class_define(
        "oculus.internal.virtual_input.ITrackingDataInjectionService", create, destroy, unused);
    if (!c || !AIBinder_associateClass(b, c)) {
        fprintf(stderr, "Interface mismatch\n");
        AIBinder_decStrong(b);
        return 1;
    }
    /* Controller writes do not require DATAINJECT. Preserve the head-tracking mode. */
    int ok = transact(b, 5, NULL, (int)restore_value, NULL, 0) == 1, frames = 0;
    printf("INJECTOR_STARTED pid=%d\n", getpid());
    fflush(stdout);
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);
    int total = (int)ceil(duration * hz);
    for (int frame = 0; ok && !stopped && frame < total; frame++) {
        if (streaming)
            stream_pose(pos, rot);
        ok = pose(b, argv[1], 1, rot, 4) && pose(b, argv[1], 0, pos, 3);
        if (!ok)
            break;
        frames++;
        long long ns = (long long)((frame + 1) * 1e9 / hz) + start.tv_nsec;
        struct timespec deadline = {start.tv_sec + ns / 1000000000LL, ns % 1000000000LL};
        while (!stopped &&
               clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, NULL) == EINTR) {
        }
    }
    int restored = transact(b, 5, NULL, (int)restore_value, NULL, 0) == 1;
    printf("accepted_frames=%d accepted_pose_calls_at_least=%d rejected_calls=%u streamed_poses=%u "
           "invalid_lines=%u restore_mode=%d restore_ok=%d interrupted=%d\n",
           frames, frames * 2, rejected_calls, streamed_poses, invalid_lines, (int)restore_value,
           restored, stopped);
    AIBinder_decStrong(b);
    dlclose(lib);
    return ok && restored ? 0 : 1;
}
