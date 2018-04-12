obj = lego pingpong draw pool ikea cooking

all: $(obj)

$(obj): gabriel-template.yaml
	sed 's/lego/$@/g' gabriel-template.yaml | tee $@-template.yaml

.PHONY: clean

clean:
	rm -f $(obj)-template.yaml
