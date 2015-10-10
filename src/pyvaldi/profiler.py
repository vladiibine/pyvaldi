class RhythmProfiler(object):
    def __init__(self):
        self.baton = None
        self.checkpoints = None
        self.checkpoint_idx = 0

    def profile(self, frame, action_string, whatever):
        if self.checkpoint_idx >= len(self.checkpoints):
            return

        current_cp = self.checkpoints[self.checkpoint_idx]

        # log_lock.acquire()
        # thread = threading.current_thread()
        # print("PROFILER: {} func: {} action: {}".format(thread.name, frame.f_code.co_name, action_string))
        # log_lock.release()
        print(frame.f_code.co_name, action_string)

        if (action_string == 'call' and current_cp.before or
                action_string == 'return' and not current_cp.before):
            if current_cp.is_reached(frame.f_code):
                self.baton.wait_for_permission(current_cp)
                self.baton.acknowledge_checkpoint(current_cp)
                # print('asdf', current_cp)
                # import  time; time.sleep(1)

                self.checkpoint_idx += 1
                if self.checkpoint_idx >= len(self.checkpoints):
                    return

                self.baton.wait_for_permission(self.checkpoints[self.checkpoint_idx])

    # def __call__(self, frame, action_string, dunno):
    #     if self.checkpoint_idx >= len(self.confirming_checkpoints):
    #         return
    #
    #     current_checkpoint = self.confirming_checkpoints[self.checkpoint_idx]
    #
    #     if current_checkpoint is None:
    #         return
    #
    #     if not current_checkpoint.is_reached(frame.f_code):
    #         return
    #
    #     if ((current_checkpoint.before and action_string == 'call') or
    #             (not current_checkpoint.before and action_string == 'return')):
    #         self.checkpoint_reached_callback(current_checkpoint)
    #         self.condition.acquire()
    #         self.condition.wait()
    #         self.condition.release()
    #
    #         self.checkpoint_idx += 1