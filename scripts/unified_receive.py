import csv
import time
import argparse
import os
import pandas as pd
from datetime import datetime
from pylsl import StreamInlet, resolve_streams
from typing import Tuple


def find_stream(stream_names: list[str]) -> Tuple[list[StreamInlet], dict]:
    """
    Finds the LSL stream by name and its info, then returns a StreamInlet
    for data collection.

    Args:
        stream_names (list[str]): The names of the stream to find.

    Returns:
        inlets (list[StreamInlet]): The inlets for the found stream.
        stream_channel_labels (dict): A dictionary of labels from each inlets
    """
    print("Looking for EEG streams")
    # Find streams and get their metadata
    inlets = []
    # Dictionary to hold channel labels for each stream
    stream_channel_labels = {}

    all_streams = resolve_streams(wait_time=5.0)

    for name in stream_names:
        stream_found = False
        for stream in all_streams:
            if stream.name() == name:
                print(f"Found stream: {name}")
                inlet = StreamInlet(stream)
                inlets.append(inlet)

                info = inlet.info()
                ch = info.desc().child("channels").child("channel")
                labels = []
                for _ in range(info.channel_count()):
                    labels.append(ch.child_value("label"))
                    ch = ch.next_sibling()
                stream_channel_labels[name] = labels
                print(f"  > Found channels: {labels}")

                stream_found = True
                break
        if not stream_found:
            print(f"Warning: Stream '{name}' not found.")

    if not inlets:
        raise RuntimeError(
            "Error: No specified LSL streams were found. Cannot continue."
        )
    return inlets, stream_channel_labels


def unified_receive(inlets: list[StreamInlet], duration: int) -> str:
    """
    Receives the information from the LSL streams, and outputs into a
    single "wide" format CSV with descriptive headers.

    Args:
        inlets (list[StreamInlet]): List of stream inlets to consume.
        duration (int): The duration of the experiment to record.

    Returns: temp_filename (str): Temporary CSV file's name
    """
    print("--- Unified Recorder ---")

    # Record data to a temporary "long" format file
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    temp_filename = f"temp-{timestamp}.csv"
    max_channels = max(inlet.info().channel_count() for inlet in inlets)
    csv_headers = ["lsl_timestamp", "stream_name"] + [
        f"value_ch{i+1}" for i in range(max_channels)
    ]

    print(f"\nRecording raw data to temporary file: {temp_filename}")
    with open(temp_filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        start_time = time.time()
        while time.time() - start_time < duration:
            for inlet in inlets:
                sample, timestamp = inlet.pull_sample(timeout=0.0)
                if sample:
                    row = [timestamp, inlet.info().name()] + sample
                    writer.writerow(row)
    print("--- Raw recording finished. ---")

    return temp_filename


def format_csv(
    final_filename_base: str, temp_filename: str, stream_channel_labels: dict
) -> None:
    """
    Reformats the CSV file data to have channels on top and the data value
    listed in columns.

    Args:
        final_filename_base (str): The final CSV file name.
        temp_filename (str): Temporary CSV file's name.
        stream_channel_labels (dict): A dictionary of labels from each inlets

    Returns: None
    """
    try:
        df = pd.read_csv(temp_filename)

        streams = {}
        for name in df["stream_name"].unique():
            stream_df = df[df["stream_name"] == name].copy()
            stream_df.drop("stream_name", axis=1, inplace=True)
            stream_df.dropna(axis=1, how="all", inplace=True)

            # Rename generic columns (value_ch1) to real channel names
            original_cols = [
                col for col in stream_df.columns if col.startswith("value_ch")
            ]
            real_labels = stream_channel_labels.get(name, [])
            # Create unique final names like "StreamName_ChannelName"
            rename_dict = {
                orig: f"{name}_{label}"
                for orig, label in zip(original_cols, real_labels)
            }
            stream_df.rename(columns=rename_dict, inplace=True)

            streams[name] = stream_df

        headset_stream_name = max(
            streams, key=lambda name: streams[name].shape[1]
        )
        marker_stream_name = min(
            streams, key=lambda name: streams[name].shape[1]
        )

        headset_df = streams[headset_stream_name]
        marker_df = streams[marker_stream_name]

        # Sort for merge_asof
        headset_df = headset_df.sort_values("lsl_timestamp")
        marker_df = marker_df.sort_values("lsl_timestamp")

        formatted_df = pd.merge_asof(
            left=headset_df,
            right=marker_df,
            on="lsl_timestamp",
            direction="backward",
            tolerance=0.5,
        )
        # Fill NaN for marker columns and set type to int
        marker_cols = [
            col for col in formatted_df.columns if marker_stream_name in col
        ]
        for col in marker_cols:
            formatted_df[col] = formatted_df[col].fillna(0).astype(int)

        timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_filename = f"{final_filename_base}-{timestamp_str}.csv"

        print(f"\nSaving formatted data to: {final_filename}")
        formatted_df.to_csv(final_filename, index=False)

    except Exception as e:
        print(f"An error occurred during formatting: {e}")
    finally:
        print(f"Cleaning up temporary file: {temp_filename}")
        os.remove(temp_filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LSL Unified Recorder and Formatter"
    )
    parser.add_argument(
        "--streams", nargs="+", required=True, help="List of LSL stream names."
    )
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Recording duration in seconds.",
    )
    parser.add_argument(
        "--filename",
        type=str,
        required=True,
        help="Base for the final output filename.",
    )

    args = parser.parse_args()
    inlets, stream_channel_labels = find_stream(args.streams)
    temp_filename = unified_receive(inlets, args.duration)
    format_csv(args.filename, temp_filename, stream_channel_labels)
