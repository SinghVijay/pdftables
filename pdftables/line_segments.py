"""
Algorithms for processing line segments

segments_generator

    Yield segments in order of their start/end.

    [(1, 4), (2, 3)] => [(1, (1, 4)), (2, (2, 3)), (3, (2, 3)), (4, (1, 4))]

histogram_segments

    Number of line segments present in each given range

    [(1, 4), (2, 3)] => [((1, 2), 1), ((2, 3), 2), ((3, 4), 1)]

segment_histogram

    Binning for a histogram and the number of counts in each bin

    [(1, 4), (2, 3)] => [(1, 2, 3, 4), (1, 2, 1)]
"""

from __future__ import division

from collections import defaultdict, namedtuple
from heapq import heappush, heapreplace, heappop


class LineSegment(namedtuple("LineSegment", ["start", "end", "object"])):

    @classmethod
    def make(cls, start, end, obj=None):
        return cls(start, end, obj)

    def __repr__(self):
        return '{0}(start={1:6.04f} end={2:6.04f} object={3})'.format(
            type(self).__name__, self.start, self.end, self.object)

    @property
    def length(self):
        return self.end - self.start

    @property
    def midpoint(self):
        return (self.start + self.end) / 2


def midpoint(segment):
    yield segment.midpoint


def start_end(segment):
    yield segment.start
    yield segment.end


def start_midpoint_end(segment):
    yield segment.start
    yield segment.midpoint
    yield segment.end


def segments_generator(line_segments, to_visit=start_end):
    """
    Given the a list of segment ranges [(start, stop)...], yield the list of
    coordinates where any line segment starts or ends along with the line
    segment which starts/ends at that coordinate. The third element of the
    yielded tuple is True if the given segment is finishing at that point.

    In [1]: list(linesegments.segments_generator([(1, 4), (2, 3)]))
    Out[1]: [(1, (1, 4), False),
             (2, (2, 3), False),
             (3, (2, 3), True),
             (4, (1, 4), True)]

    The function ``to_visit`` specifies which positions will be visited for
    each segment and may be ``start_end`` or ``start_midpoint_end``.

    If ``to_visit`` is a dictionary instance, it is a mapping from
    ``type(segment)`` onto a visit function. This allows passing in both
    line segments and points which should be visited simultaneously, for
    example, to classify points according to which line segments are currently
    overlapped.
    """

    # Queue contains a list of outstanding segments to process. It is a list
    # of tuples, [(position, (start, end)], where (start, end) represents one
    # line-segment. `position` is the coordinate at which the line-segment) is
    # to be considered again.
    queue = []

    _to_visit = to_visit

    # (Note, this has the effect of sorting line_segments in start order)
    for segment in line_segments:
        if isinstance(to_visit, dict):
            _to_visit = to_visit[type(segment)]

        # an iterator representing the points to visit for this segment
        points_to_visit = _to_visit(segment)
        try:
            start = points_to_visit.next()
        except StopIteration:
            continue

        heappush(queue, (start, points_to_visit, segment))

    # Process outstanding segments until there are none left
    while queue:

        # Get the next segment to consider and the position at which we're
        # considering it
        position, points_to_visit, segment = heappop(queue)

        try:
            point_next_position = points_to_visit.next()
            if point_next_position < position:
                raise RuntimeError("Malformed input: next={0} < pos={1}"
                                   .format(point_next_position, position))
        except StopIteration:
            # No more points for this segment
            disappearing = True
        else:
            disappearing = False
            heappush(queue, (point_next_position, points_to_visit, segment))

        yield position, segment, disappearing


def histogram_segments(segments):
    """
    Given a list of histogram segments returns ((start, end), n_segments)
    which represents a histogram projection of the number of
    segments onto a line.

    In [1]: list(linesegments.histogram_segments([(1, 4), (2, 3)]))
    Out[1]: [((1, 2), 1), ((2, 3), 2), ((3, 4), 1)]
    """

    # sum(.values()) is the number of segments within (start, end)
    active_segments = defaultdict(int)

    consider_segments = list(segments_generator(segments))

    # TODO(pwaller): This function doesn't need to consider the active segments
    # It should just maintain a counter. (expect a ~O(10%) speedup)

    # Look ahead to the next start, and that's the end of the interesting range
    for this, next in zip(consider_segments, consider_segments[1:]):

        # (start, end) is the range until the next segment
        (start, seg, disappearing), (end, _, _) = this, next

        # Did the segment appear or disappear? Key on the segment coordinates
        if not disappearing:
            active_segments[seg] += 1

        else:
            active_segments[seg] -= 1

        if start == end:
            # This happens if a segment appears more than once.
            # Then we don't care about considering this zero-length range.
            continue

        yield (start, end), sum(active_segments.values())


def hat_point_generator(line_segments):
    """
    This is a hat for one line segment:

             /\
        ____/  \____

            |  |
            |  \_ End
            \_ Start

        position --->

    This generator yields at every `position` where the value of the hat
    function could change.
    """

    # Invariants:
    # * Position should be always increasing
    # * First and last yielded points should always be the empty set.
    # * All yielded positions should lie within all LineSegments in the
    #   `active_segments` at the point it is yielded
    # * Each yielded set has its own id()

    # Set of segments active yielded for unique values of `position`
    active_segments = set()
    # Set of segments which have appeared so far at this `position`
    new_segments = set()

    segments_by_position = segments_generator(
        line_segments, start_midpoint_end)
    last_position = None

    for position, segment, disappearing in segments_by_position:

        if segment.start == segment.end:
            # Zero-length segments are uninteresting and get skipped
            continue

        if last_position is not None and last_position != position:

            # Sanity check.
            assert all(s.start <= last_position < s.end
                       for s in active_segments)

            # Copy the `active_segments` set so that the caller doesn't
            # accidentally end up with the same set repeatedly and can't
            # modify the state inside this function
            yield last_position, set(active_segments)

            # `new_segments` are now `active segments.
            active_segments |= new_segments
            new_segments.clear()

        if disappearing:
            # This is the end of the segment, remove it from the active set
            active_segments.remove(segment)
        else:
            # Record the segment in the seen list. It might be the start or
            # midpoint. If it's the start, it won't be `active` until the
            # next iteration (unless that iteration removes it).
            new_segments.add(segment)

        last_position = position

    # For completeness, yield empty set at final position.
    yield last_position, set()


def hat(segment, position):
    """
    This function returns 0 when ``position` is the start or end of ``segment``
    and 1 when ``position`` is in the middle of the segment.

           /\
        __/  \__
    """
    h = abs((segment.midpoint - position) / segment.length)
    return max(0, 1 - h)


def normal_hat(position, active_segments):
    """
    The ``normal_hat`` is the sum of the hat function for all active segments
    at this position
    """
    return sum(hat(s, position) for s in active_segments)


def max_length(position, active_segments):
    """
    Returns the maximum length of any segment overlapping ``position``
    """
    if not active_segments:
        return None
    return max(s.length for s in active_segments)


def normal_hat_with_max_length(position, active_segments):
    """
    Obtain both the hat value and the length of the largest line segment
    overlapping each "hat position".
    """

    return (normal_hat(position, active_segments),
            max_length(position, active_segments))


def hat_generator(line_segments, value_function=normal_hat):
    """
    The purpose of this function is to determine where it might be effective
    to clamp text to for the purposes of text visitation order.

    The hat generator returns the sum of ``hat`` at each position where any
    line segment's ``start``, ``midpoint`` or ``end`` is.

    ``value_function`` can be used to obtain different kinds of information
    from the ``hat_point_generator``'s points.
    """

    for position, active_segments in hat_point_generator(line_segments):
        yield position, value_function(position, active_segments)


def segment_histogram(line_segments):
    """
    Binning for a histogram and the number of counts in each bin.
    Can be used to make a numpy.histogram.

    In [1]: list(linesegments.histogram_segments([(1, 4), (2, 3)]))
    Out[1]: [(1, 2, 3, 4), (1, 2, 1)]
    """
    data = list(histogram_segments(line_segments))

    if not data:
        return [(), ()]

    x, counts = zip(*data)
    starts, ends = zip(*x)

    return starts + (ends[-1],), counts


def above_threshold(histogram, threshold):
    """
    Returns a list of line segments from histogram which are above threshold
    """

    bin_edges, bin_values = histogram
    edges = zip(bin_edges, bin_edges[1:])

    above_threshold = []

    for (first, second), value in zip(edges, bin_values):
        if value < threshold:
            continue

        if above_threshold and above_threshold[-1].end == first:
            # There's a previous one we can extend
            above_threshold[-1] = above_threshold[-1]._replace(
                end=second)
        else:
            # Insert a new one
            above_threshold.append(LineSegment(first, second, None))

    return above_threshold


def find_peaks(position_values):
    """
    Find all points in a peaky graph which are local maxima.

    This function assumes that the very first and last points can't be peaks.
    """

    # Initial value is zero, up is the only direction from here!
    increasing = True

    # The loop has two states. Either we're going up, in which case when we see
    # a next value less than the current one, we must be at the top. At which
    # point it's down hill and all next values will be less than the current
    # one. Until the bottom is reached, at which point we're increasing again.

    # Note that the last `position` can never be yielded.

    successive_pairs = zip(position_values, position_values[1:])
    for (position, value), (_, next_value) in successive_pairs:
        if increasing:
            if next_value < value:
                # position is a peak
                increasing = False
                yield position

        else:
            if next_value > value:
                # position is a trough
                increasing = True
