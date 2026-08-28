#!/bin/bash


redis-cli EVAL "$(cat list-loop-and-push.lua)" 1 "mylist" 1000
