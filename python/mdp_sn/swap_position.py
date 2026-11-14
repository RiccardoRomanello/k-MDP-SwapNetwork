from . import verifier as SNV
class SwapAndPosition:
    class _Swapper:
        # Data can also be a simple array...
        def __init__(self, data, verifier: SNV.SwapNetworkVerifier):
            self.arr = data
            self.swaps = 0
            self.n = len(self.arr)
            self.verifier = verifier

        def swap(self, i):
            if i < 0 or i >= self.n - 1:
                raise ValueError(f"Invalid swap index {i}")
            
            self.arr[i], self.arr[i+1] = self.arr[i+1], self.arr[i]
            self.swaps += 1
            
            self.verifier.swap(self.arr[i], self.arr[i+1])

        def move_element(self, current_idx, target_idx):
            """Bubbles element from current index to target index."""
            if current_idx < target_idx:
                for i in range(current_idx, target_idx):
                    self.swap(i)
            else:
                for i in range(current_idx, target_idx, -1):
                    self.swap(i - 1)

        def invert_segment_lr(self, start, end):
            """
            Left-to-Right Inversion (e.g. ABC -> BAC -> BCA -> CBA)
            Bubbles the element at 'start' to 'end-1' repeatedly.
            """
            seg_len = end - start
            for i in range(seg_len - 1):
                self.move_element(start, end - 1 - i)

        def invert_segment_rl(self, start, end):
            """
            Right-to-Left Inversion (e.g. DEF -> DFE -> FDE -> FED)
            Bubbles the element at 'end-1' to 'start' repeatedly.
            """
            seg_len = end - start
            for i in range(seg_len - 1):
                # Move the last element of the current unsorted segment to the front
                # The 'last' element is always at 'end-1'
                # The target front is 'start + i'
                self.move_element(end - 1, start + i)

        def get_result(self):
            return "".join(self.arr) if self.arr and isinstance(self.arr[0], str) else self.arr

    # ######################################################################### #
    #        Swap-and-Position          #
    # ######################################################################### #

    # Swap-and-Position on the backbone
    def run(data, verifier):
        s = SwapAndPosition._Swapper(data, verifier)
        SwapAndPosition._run_logic(s, 0, len(data))
        # return s.get_result(), s.swaps
        return s.swaps, s.get_result()

    def _run_logic(s, start, end):
        length = end - start
        if length <= 1:
            return

        if length % 2 == 0:
            # === EVEN CASE ===
            mid = start + length // 2
            
            # 1. Invert Left (LR) and Right (RL)
            s.invert_segment_lr(start, mid) # ABC -> CBA
            s.invert_segment_rl(mid, end)   # DEF -> FED
            
            # 2. Interleave (Cross-Move)
            half_len = length // 2
            for _ in range(half_len):
                # Move Right-side head (which is at 'mid') to Left-side head ('start')
                s.move_element(mid, start)
                # Move Left-side head (which pushed to 'mid') to Right-side tail ('end-1')
                s.move_element(mid, end - 1)
                
        else:
            # === ODD CASE ===
            # Split: Left gets extra char
            split_len = (length + 1) // 2
            mid = start + split_len
            
            # 1. Invert Left (LR) and Right (RL)
            s.invert_segment_lr(start, mid) # ABCD -> DCBA
            s.invert_segment_rl(mid, end)   # EFG -> GFE
            
            # 2. Move Right Part to Left
            # Logic: GFE moves to front. G (at mid) moves to start. 
            # Then F (now at mid+1) moves to start (pushing G). 
            # Result is GFE DCBA? No, let's trace the loop.
            # If we move `mid` to `start` repeatedly, we reverse the order of the block being moved.
            # If we move `mid+k` to `start`, we preserve order.
            # The prompt trace: "DCBA GFE -> DCBGAFE -> ... -> GDCBAFE". 
            # This moves G (at mid) to start.
            # Then F: "GDCBAFE -> GDCBFAE -> ... -> FGDCBAE".
            # This moves F (at mid+1) to start.
            # So we iterate through the right block and move each element to 'start'.
            right_len = end - mid
            for k in range(right_len):
                # The element to move is technically always at 'mid + k'
                # because we inserted 'k' elements before the original left block.
                s.move_element(mid + k, start)
                
            # 3. Invert the New Right Side (RL)
            # The new right side corresponds to the OLD left side (DCBA).
            # It is located from 'start + right_len' to 'end'.
            # Prompt: "DCBA -> ... -> ABDC/ABCD". (Right-to-Left Inversion)
            new_right_start = start + right_len
            s.invert_segment_rl(new_right_start, end)

    # ######################################################################### #
    #                  Code to handle the all-to-all constraints                #
    # ######################################################################### #

    def acquaint(data, verifier):
        s = SwapAndPosition._Swapper(data, verifier)
        SwapAndPosition._acquaint(data, s)
        return s.swaps, s.get_result()
    
    def _acquaint(data, swapper):
        A = list(data)
        n = len(A)
        pos = {A[i]: i for i in range(n)}   # current positions
        swaps = []

        def do_swap(i: int):
            # swap positions i and i+1
            x, y = A[i], A[i+1]
            A[i], A[i+1] = y, x
            swapper.swap(i)
            pos[x], pos[y] = i+1, i
            swaps.append(i)

        # Process k from 3 to n (1-based), i.e. original labels arr[k-1]
        for k in range(3, n+1):
            label = data[k-1]        # original k-th element
            cur = pos[label]
            # By invariant (see proof) cur == k-1, but we read current pos for safety.
            # Move it left until index 1 (i.e., second position)
            while cur > 1:
                do_swap(cur-1)
                cur -= 1
