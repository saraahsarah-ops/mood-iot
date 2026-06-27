import { beforeEach, describe, expect, it } from "vitest";

import { useMessageStore, useNotifStore } from "@/lib/store";

describe("useNotifStore", () => {
  beforeEach(() => useNotifStore.setState({ items: [] }));

  it("setItems + unreadCount compte les non-lues", () => {
    useNotifStore.getState().setItems([
      { id: "1", status: "sent" },
      { id: "2", status: "read" },
      { id: "3", status: "pending" },
    ] as any);
    expect(useNotifStore.getState().unreadCount()).toBe(2);
  });

  it("markRead marque une notif comme lue", () => {
    useNotifStore.getState().setItems([{ id: "1", status: "sent" }] as any);
    useNotifStore.getState().markRead("1");
    expect(useNotifStore.getState().items[0].status).toBe("read");
  });

  it("markAllRead marque tout comme lu", () => {
    useNotifStore.getState().setItems([
      { id: "1", status: "sent" },
      { id: "2", status: "pending" },
    ] as any);
    useNotifStore.getState().markAllRead();
    expect(useNotifStore.getState().unreadCount()).toBe(0);
  });
});

describe("useMessageStore", () => {
  beforeEach(() => useMessageStore.setState({ conversations: {} }));

  it("addMessage ajoute a la conversation du patient", () => {
    useMessageStore.getState().addMessage("p1", { id: "m1", content: "salut" } as any);
    useMessageStore.getState().addMessage("p1", { id: "m2", content: "ca va ?" } as any);
    expect(useMessageStore.getState().conversations.p1).toHaveLength(2);
  });
});
