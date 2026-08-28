**A Process for**

**Automatic Security Privilege Escalation and Revocation**

**The challenge**

Within any large organization there is always a tension between giving too much, or too little, access to individuals or groups so they can fulfil their normal role obligations.

Periodic review of security privileges and access levels is best practice, and such a review was recently applied across the organization. As part of that, some access that had been granted informally got dialed back, and the number of people who could grant elevated access was narrowed.

Certain work functions such as team-based ticket duty rotations, operations on-call rostering, and incident triage, management and remediation will typically feature situations where a higher level of access privilege is needed (see Table 2). And crucially, this additional access is usually only needed for a bounded period of time.

These are well known and understood use cases that had thrown up some challenges around compliance; challenges that resulted in systems' access being tightened and a narrowing of who could help grant additional access privileges as needed. Consider,

**Elevating access to manage core services and operations**

When additional access was needed, an ops team could previously grant it for a period. Problems with that approach include:

1. Multiple manual steps were needed.
2. Multiple systems were involved — LDAP, GitHub, Chef, etc.
3. Separation of concerns and least privilege issues were apparent.
4. The oversight and approval process was patchy, inconsistent, and not well advertised.
5. Elevated privileges were being left in place due to insufficient cleanup after the initial access period had expired.

Table 1 — Typical Security-related Tasks and Actors

|  | LDAP – Via rake task  | Config Management (e.g. Chef/GitHub)  | Actors Old | Actors New |
| ----- | ----- | :---- | :---- | ----- |
| **Manage GROUP Access** | rake user:group\_add / rake user:group\_remove | Chef Role — Adds user via Attributes | Ops/SRE, Security, NOC | ~~Ops/SRE~~  Security, NOC |
| **Manage SUDO Access** | rake policy:sudo\_add / rake policy:sudo\_remove |  | Ops/SRE, Security, NOC | ~~Ops/SRE~~  Security, NOC |
| **Manage USER Access** | rake user:user\_add / rake user:user\_remove |  | Ops/SRE, Security, NOC | ~~Ops/SRE~~  Security, NOC |

Table 2 — Typical activities needing elevated privileges

| Activity  | Description  | Frequency  | Actor |
| :---- | :---- | :---- | :---- |
| **Calls to shared services** | Interaction with databases, Redis etc. | Consistent but periodic | Ticket duty, Developers |
| **Utility functions such as cache clearing, job/task running** | Housekeeping that occurs on a regular basis — both proactive and reactive | Consistent | Ticket duty, Developers |
| **Report generation** | Periodic reports running for internal and external consumption | Consistent but periodic | Ticket duty, Advocates, Developers |
| **Modifying log levels temporarily** | Debug aid for incident management and investigation | Infrequent | Ticket Duty, Developers |
| **System and/or account migration** | Migration of accounts, old to new | Infrequent but periodic | Developers, Remediation, Advocates, Ticket Duty |
| **Kafka CLI tools** | Needed to interact with Kafka managers etc. | Consistent but periodic | Developers, Ticket Duty |
| **Deployment failure debugging** | Sometimes deploys break and bypassing automation helps remediation velocity | Infrequent but periodic | Developers |
| **Backfill tasks (accounts)** | Remediation actions needed to restore account consistency after one or more service failures | Infrequent but periodic | Advocates, Developers |
| **Service restarts** | Caused by high loads, hung tasks etc. | Infrequent | Developers |
| **Jump box capability to enable access to legacy systems** | Access to older parts of the platform | Occasional | Developers, Ticket Duty |
| **Real-time debugging access** | Incident management and problem investigation | Infrequent but periodic | Developers |
| **Audit log execution and export** | Compliance and oversight reasons | Infrequent but periodic | Ticket Duty, Developers |

**What changed?**

1. The ops team used to have admin capabilities to interact with LDAP. This allowed setting up new team members, adding/rotating SSH keys, management of LDAP groups, managing SUDO access etc. Compliance and security requirements have necessitated the removal of this capability from the ops team.

*Figure 1 — /etc/ssh/sshd\_config Allowed groups — old*

2. All developers had the ability to SSH to the 'deploy' box in staging and/or production. A deploy box can act as a jumpbox to other servers, typically via 'su' to the backend user. This access is no more, and temporarily re-enabling it via the ops team is no longer possible due to point 1 above.

*Figure 2 — /etc/ssh/sshd\_config Allowed groups — new*

**A possible solution**

Can we come up with a username-centric automated workflow that incorporates:

1. A two-step approval
2. Adding a user to a pre-defined LDAP group (which maps to a unix group) for a defined period of time, and
3. Automatically removing the user once the permission window has expired.

**Step 1 — Create & Approve a Ticket**

The **Requester** (e.g. `@alice`) who needs additional access creates a ticket in your issue tracker (Jira, Linear, etc.), specifying what additional access they require, for what reason, and for how long (e.g. 1 week). An **Approver** (line manager or surrogate) must be nominated. The options to choose an Approver from should be presented as a pre-populated list.

This **Approver** will receive a request with the next status being approve or deny — standard workflow stuff.

On selecting **Approve**, a callback is triggered (via webhook) into a secondary system. This callback also sends a private **Slack message** (via a bot) to the Approver, again outlining the request and soliciting an Approve/Deny.

Note: This second Slack approval step can be useful in protecting the primary system should the issue tracker be compromised — it decouples third-party services by requiring an additional confirmation from a human.

**Step 2 — Inspect and Approve the Slack Message**

Here the **Approver** will further review and Approve/Deny the request. The user can select an approval window that is either "until a certain time and date" or "for a certain period from the request time". Examples:

- Until 2PM December 12
- For 2 hours
- For 1 week

Human-readable timestamps are fine here.

**Step 3 — Automate the implementation of the approved request**

**Redis** is the ***key*** to making this solution work.

Redis has a built-in garbage collection loop and the notion of a key having a set TTL. Once the Time To Live EXPIREs, Redis does some clean up — and the nice thing is it can notify us about this. Command-wise, we use a combination of `SET`, `EXPIRE`, and KeySpace Event notifications. When a key expires, Redis can be configured to trigger events that can be `SUBSCRIBE`d to. On receipt of an expire event we can trigger a process to remove the user from the group (e.g. the LDAP-managed `temp_access_backend` group).

Imagine we have a key in Redis that represents the group and username to be given access. Here are some examples using `redis-cli` (in reality this would be coded up):

Assume the following groups have been previously added to `/etc/ssh/sshd_config`:

*Figure 3 — Three new example groups*

First, tell the Redis server we want Keyspace events:

```
# Tell redis we want keyevent notifications
127.0.0.1:6379> config set notify-keyspace-events KEA
```

Where **KEA** means we're interested in all events from Redis Keyspace Notifications. If using Redis via AWS ElastiCache, enable this via the **notify-keyspace-events** parameter in the Parameter Group.

Set the requester's key details. In database **10** — create a key string of `group:username` and SET its value to the URL of the access request ticket. Also add it to database **9** (without expiry, as a permanent audit record). Note EXPIRY is set to 3600 seconds:

```
# Set the key for this user:group pair
127.0.0.1:6379[10]> SET temp_access_backend:alice https://jira.example.com/TICKET-123 EX 3600
127.0.0.1:6379[9]>  SET temp_access_backend:alice https://jira.example.com/TICKET-123
```

Subscribe to see when key expiry events fire:

```
# Subscribe to all events
~$ redis-cli --csv psubscribe '__key*__:*'

Reading messages... (press Ctrl-C to quit)

"psubscribe","__key*__:*",1

"pmessage","__key*__:*","__keyspace@10__:temp_access_backend:alice","set"
"pmessage","__key*__:*","__keyevent@10__:set","temp_access_backend:alice"
"pmessage","__key*__:*","__keyspace@10__:temp_access_backend:alice","expire"
"pmessage","__key*__:*","__keyevent@10__:expire","temp_access_backend:alice"

... TIME PASSES ...

"pmessage","__key*__:*","__keyspace@10__:temp_access_backend:alice","expired"
"pmessage","__key*__:*","__keyevent@10__:expired","temp_access_backend:alice"
```

A bunch of things happened here. We asked for notifications on everything so we got them all. Note how the Redis database number (10) is part of both the keyspace event and the keyevent event. On first glance the names key***space*** and key***event*** look similar enough to skim past in the docs, but they're distinct — keyspace events are namespaced by key, keyevent events are namespaced by event type.

**Responding to a keyspace event with a server-side Redis Lua Script**

A nice feature of Redis is its built-in Lua scripting engine. Lua is a fast, C-based interpreted language used widely across the internet, and support for it was built into Redis some time back. Redis gives us two command options: `EVAL` and `EVALSHA`.

`EVAL` takes a stringified Lua script, sends it to the Redis server, and executes it. `EVALSHA` is slightly different — it expects a SHA hash representing a Lua script previously loaded via `SCRIPT LOAD`; think stored procedure in MySQL. The key point is the script executes in the database/server context.

**How does it help with automating temporary privilege escalation and revocation?**

**Adding a user to a group**

The pattern goes something like this. On an access-controlled server (owned by the security team), a Process/Agent is listening — perhaps a Python or Java program with a Redis binding. This Agent receives the approved access request. The same Agent has `SUBSCRIBE`d to KeyEvents from Redis in a separate thread, filtered to only the events and databases we care about (to reduce noise).

A `SET` is done which stores the `group:username` + duration into Redis Database 10:

```
SELECT 10; SET temp_access_backend:alice 'some.value.or.other'
```

This triggers a `"__keyevent@10__:set","temp_access_backend:alice"` message. The subscriber receives this and copies the key data to Redis Database 9 (without expiration) as a permanent audit record.

The Agent then makes an `LDAP_GROUP_ADD` call to add `alice` to the LDAP group `temp_access_backend` — which was already known to `sshd_config` as an AllowedGroup.

**Removing a user from a group**

Once the TTL goes to zero, a keyevent fires:

```
"__keyevent@10__:expired","temp_access_backend:alice"
```

The PUB/SUB subscriber thread in the Agent receives this, parses the key name `temp_access_backend:alice`, and makes an `LDAP_GROUP_REMOVE` call to remove `alice` from the LDAP group `temp_access_backend`.

Because the key has expired it's no longer in Redis Database 10, but we copied it to Database 9 earlier so the audit record (e.g. a link to the original ticket) is still there.

**Auditing and failsafe / periodic sync to LDAP**

Redis PUB/SUB is best-effort. An agent could crash and miss an event. Since we have all live keys in DB 10, we can periodically do a `KEYS temp_access_backend:*` and replace the LDAP group membership with the current usernames returned — ensuring the two stay in sync.

**IAM/RBAC considerations**

Before a more mature solution can be approved there will need to be a careful analysis of the RBAC requirements and IAM posture more generally — especially if there's a mix of internal and third-party systems in play. I would anticipate this covering host security, access control, and sensible values for resource and identity-based policies, and I'd expect to defer to the security team for their best advice here, along with a security review from product security.

**Very Basic POC**

I've done a really basic POC to validate the core Redis pub/sub mechanics. You can find it in the `pubsub-agent` repository.
