import { useEffect, useRef, useState } from "react";

import {
  audioLineUrl,
  gapMs,
  type AudioManifest,
  type AudioSequenceItem,
} from "../../api/audio";
import { ApiError } from "../../api/client";
import { runAiJob } from "../../api/conversations";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Button, Field } from "../../components/ui";
import {
  useAudioManifest,
  useDeleteAudio,
  useGenerateAudio,
  useGenerateAudioLine,
  usePatchAudioLine,
} from "../../queries/audio";
import { useJobs } from "../../queries/settings";

const STATUS_STYLE: Record<string, string> = {
  new: "bg-attn-wash text-attn",
  regenerate: "bg-attn-wash text-attn",
  unchanged: "bg-ok-wash text-ok",
};

export function AudioModal({
  bookId,
  sceneId,
  onClose,
  onOpenConversation,
}: {
  bookId: string;
  sceneId: string;
  onClose: () => void;
  onOpenConversation: (conversationId: string) => void;
}) {
  const toast = useToast();
  const manifestQ = useAudioManifest(bookId, sceneId);
  const generateAll = useGenerateAudio(bookId, sceneId);
  const generateLine = useGenerateAudioLine(bookId, sceneId);
  const patchLine = usePatchAudioLine(bookId, sceneId);
  const deleteAudioMut = useDeleteAudio(bookId, sceneId);
  const jobs = useJobs();
  const audioJob = (jobs.data ?? []).find((j) => j.outputType === "audio-script");

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [playIndex, setPlayIndex] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const gapTimer = useRef<number | null>(null);

  const manifest = manifestQ.data;

  useEffect(() => {
    return () => {
      if (gapTimer.current) window.clearTimeout(gapTimer.current);
      audioRef.current?.pause();
    };
  }, []);

  async function onGenerateScript() {
    if (!audioJob) {
      toast.error("Define an audio-script AI-Job in Settings → AI-Jobs first.");
      return;
    }
    try {
      const { conversationId } = await runAiJob(bookId, {
        aiJobId: audioJob.id,
        sceneId,
        scope: "full",
      });
      onOpenConversation(conversationId);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start audio-script job");
    }
  }

  function stopPlaylist() {
    setPlaying(false);
    if (gapTimer.current) window.clearTimeout(gapTimer.current);
    audioRef.current?.pause();
  }

  function playScene() {
    if (!manifest) return;
    const playlist = manifest.sequence.filter((i) => i.renderedFile);
    if (playlist.length === 0) {
      toast.error("No line audio yet — generate pending lines first.");
      return;
    }
    stopPlaylist();
    setPlaying(true);
    setPlayIndex(0);
    playAt(playlist, 0);
  }

  function playAt(playlist: AudioSequenceItem[], index: number) {
    const item = playlist[index];
    if (!item?.renderedFile) {
      setPlaying(false);
      return;
    }
    setPlayIndex(index);
    const el = audioRef.current ?? new Audio();
    audioRef.current = el;
    el.src = audioLineUrl(bookId, sceneId, item.renderedFile);
    el.onended = () => {
      const next = index + 1;
      if (next >= playlist.length) {
        setPlaying(false);
        return;
      }
      const wait = gapMs(item, playlist[next]);
      gapTimer.current = window.setTimeout(() => playAt(playlist, next), wait);
    };
    void el.play().catch(() => {
      setPlaying(false);
      toast.error("Playback failed");
    });
  }

  function playOne(item: AudioSequenceItem) {
    if (!item.renderedFile) return;
    stopPlaylist();
    const el = audioRef.current ?? new Audio();
    audioRef.current = el;
    el.src = audioLineUrl(bookId, sceneId, item.renderedFile);
    el.onended = null;
    void el.play();
  }

  return (
    <Modal title="Scene audio" onClose={onClose} width={880}>
      <div className="flex flex-wrap items-center gap-2 border-b border-line pb-3">
        <Button variant="secondary" onClick={() => void onGenerateScript()}>
          Generate script
        </Button>
        <Button
          variant="primary"
          disabled={!manifest || generateAll.isPending || manifest.synthesisStatus === "running"}
          onClick={() =>
            generateAll.mutate(undefined, {
              onError: (e) => toast.error(e instanceof ApiError ? e.message : "Generate failed"),
            })
          }
        >
          {manifest?.synthesisStatus === "running" ? "Generating…" : "Generate all pending"}
        </Button>
        {playing ? (
          <Button variant="secondary" onClick={stopPlaylist}>
            Stop
          </Button>
        ) : (
          <Button variant="secondary" disabled={!manifest} onClick={playScene}>
            Play scene
          </Button>
        )}
        {manifest && (
          <Button variant="ghost" className="!text-danger ml-auto" onClick={() => setConfirmDelete(true)}>
            Delete audio
          </Button>
        )}
      </div>

      {manifestQ.isLoading && <p className="mt-4 text-[0.875rem] text-ink-soft">Loading…</p>}

      {!manifestQ.isLoading && !manifest && (
        <div className="mt-6 space-y-2 text-center">
          <p className="text-[0.875rem] text-ink-soft">No audio script yet for this scene.</p>
          <Button variant="primary" onClick={() => void onGenerateScript()}>
            Generate script
          </Button>
        </div>
      )}

      {manifest && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap gap-3 text-[0.75rem] text-ink-soft">
            <span>{manifest.title || "Untitled"}</span>
            <span>rev {manifest.revision}</span>
            <span className="font-mono">{manifest.synthesisStatus}</span>
            {playing && <span className="text-accent">playing line {playIndex + 1}</span>}
            {manifest.lastError && <span className="text-danger">{manifest.lastError}</span>}
          </div>
          <div className="max-h-[55vh] space-y-3 overflow-y-auto pr-1">
            {manifest.sequence.map((item) => (
              <LineRow
                key={item.id}
                item={item}
                speakers={manifest.speakers}
                busy={generateLine.isPending}
                onPlay={() => playOne(item)}
                onRegen={() =>
                  generateLine.mutate(item.id, {
                    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Regen failed"),
                  })
                }
                onSave={(body) =>
                  patchLine.mutate(
                    { itemId: item.id, body },
                    { onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed") },
                  )
                }
              />
            ))}
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Delete scene audio?"
          message="Moves the audio folder to trash. The script and mp3s can be regenerated."
          confirmLabel="Delete"
          onConfirm={() => {
            setConfirmDelete(false);
            deleteAudioMut.mutate(undefined, {
              onSuccess: () => toast.success("Audio deleted"),
              onError: (e) => toast.error(e instanceof ApiError ? e.message : "Delete failed"),
            });
          }}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </Modal>
  );
}

function LineRow({
  item,
  speakers,
  busy,
  onPlay,
  onRegen,
  onSave,
}: {
  item: AudioSequenceItem;
  speakers: AudioManifest["speakers"];
  busy: boolean;
  onPlay: () => void;
  onRegen: () => void;
  onSave: (body: { text?: string; voice_settings?: { stability: number; similarity_boost: number } }) => void;
}) {
  const [text, setText] = useState(item.text);
  const [stability, setStability] = useState(item.voice_settings?.stability ?? 0.5);
  const name =
    (item.speaker_id && speakers[item.speaker_id]?.name) || item.speaker || item.speaker_id || "sfx";

  useEffect(() => {
    setText(item.text);
    setStability(item.voice_settings?.stability ?? 0.5);
  }, [item.text, item.voice_settings?.stability, item.id]);

  return (
    <div className="rounded-control border border-line bg-paper p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[0.75rem]">
        <span className="font-medium text-ink">{name}</span>
        <span className="rounded-full bg-accent-wash px-2 py-0.5 text-accent">{item.type}</span>
        <span className={`rounded-full px-2 py-0.5 ${STATUS_STYLE[item.generation_status] ?? ""}`}>
          {item.generation_status}
        </span>
        <div className="ml-auto flex gap-1">
          <Button variant="ghost" disabled={!item.renderedFile} onClick={onPlay}>
            Play
          </Button>
          <Button variant="ghost" disabled={busy} onClick={onRegen}>
            Regenerate
          </Button>
        </div>
      </div>
      <textarea
        className="mb-2 w-full rounded-control border border-line bg-surface px-2 py-1.5 font-prose text-[0.875rem] text-ink outline-none focus:border-accent"
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          if (text !== item.text) onSave({ text });
        }}
      />
      {item.type !== "sfx" && (
        <Field label={`Stability ${stability.toFixed(2)}`}>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={stability}
            className="w-full"
            onChange={(e) => setStability(Number(e.target.value))}
            onMouseUp={() => {
              if (stability !== (item.voice_settings?.stability ?? 0.5)) {
                onSave({
                  voice_settings: {
                    stability,
                    similarity_boost: item.voice_settings?.similarity_boost ?? 0.75,
                  },
                });
              }
            }}
          />
        </Field>
      )}
      {!item.renderedFile && <p className="mt-1 text-[0.75rem] text-ink-faint">No audio yet</p>}
    </div>
  );
}
